"""검증: 폐지 종목의 폐지 직전 OHLCV 특성
근본: 자격 필터가 실제 폐지 예정 종목을 얼마나 걸러내는가

방법:
  1. 폐지 종목 = 마지막 거래일이 2024-06-30 이전 (확실한 폐지)
  2. 각 폐지 종목의 마지막 거래일 기준 직전 N일 OHLCV 측정
     - N=5, 20, 60, 120 (1주/1개월/3개월/6개월 전)
  3. 각 시점에서 가격/거래량/변동성 분포
  4. 자격 필터 통과율: price>=1000 AND volume>=50000 동시 만족 비율

비교군:
  - 생존 종목 샘플 (2026-04-17까지 거래 중)의 random 시점 같은 지표
"""
import sqlite3
import numpy as np
import random

DB = r'D:\StockAnalyst\ohlcv_long.db'
conn = sqlite3.connect(DB, timeout=30)

# 1. 폐지 종목과 생존 종목 분류
codes_info = conn.execute("""
    SELECT code, MIN(date) as first_d, MAX(date) as last_d, COUNT(*) as days
    FROM daily_ohlcv_long
    WHERE code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
    GROUP BY code
    HAVING days >= 120
""").fetchall()

DELIST_CUTOFF = '20240630'  # 이 이전에 마지막 거래 = 폐지
delisted = [(c, fd, ld, days) for c, fd, ld, days in codes_info if ld < DELIST_CUTOFF]
survivors = [(c, fd, ld, days) for c, fd, ld, days in codes_info if ld >= '20260101']

print(f'전체 분석 가능 종목(>=120일): {len(codes_info):,}')
print(f'폐지 종목 (last < 2024-06-30): {len(delisted):,}')
print(f'생존 종목 (last >= 2026-01-01): {len(survivors):,}')
print()


# 2. 폐지 종목 각각의 마지막 거래일 기준 N영업일 전 OHLCV 수집
def get_nth_before(code, last_date, n):
    """code의 last_date 기준 직전 n번째 영업일 (오늘이 1번째면 n=5는 5일 전)"""
    r = conn.execute("""
        SELECT date, close, volume, high, low, open
        FROM daily_ohlcv_long
        WHERE code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
    """, (code, last_date, n)).fetchall()
    return r  # 최신부터 역순


# 각 시점별 지표 집계
# {N: {'prices':[], 'volumes':[], 'zero_vol_count':n, 'total':n, 'pass_filter':n}}
def make_slot():
    return {'prices': [], 'volumes': [],
            'returns_to_last': [],  # 해당 시점 close vs 마지막 close 수익률
            'zero_vol_count': 0, 'total': 0, 'pass_filter': 0}

N_BEFORE = [5, 20, 60, 120]  # 1주, 1개월, 3개월, 6개월
delist_agg = {n: make_slot() for n in N_BEFORE}
surv_agg = {n: make_slot() for n in N_BEFORE}

# 폐지 종목
for i, (code, fd, ld, days) in enumerate(delisted, 1):
    rows = get_nth_before(code, ld, max(N_BEFORE) + 1)
    if not rows:
        continue
    last_close = rows[0][1]

    # 각 N-n번째 날 정보 추출
    for n in N_BEFORE:
        if len(rows) <= n - 1:
            continue
        # rows[0] = 마지막(d-0), rows[n-1] = d-n+1일전, rows[n] = d-n 영업일 전
        d, c, v, h, l, o = rows[n]
        s = delist_agg[n]
        s['total'] += 1
        if c and c > 0:
            s['prices'].append(c)
        if v is not None:
            s['volumes'].append(v)
            if v == 0:
                s['zero_vol_count'] += 1
        if c > 0 and last_close and last_close > 0:
            s['returns_to_last'].append((last_close / c - 1) * 100)
        # 필터 통과
        if c >= 1000 and v >= 50000:
            s['pass_filter'] += 1

    if i % 100 == 0:
        print(f'  폐지 {i}/{len(delisted)} 진행')

print(f'\n폐지 종목 집계 완료')


# 생존 종목 (동일 개수 랜덤 샘플로 편향 방지)
random.seed(42)
survivor_sample = random.sample(survivors, min(len(delisted), len(survivors)))

# 생존 종목은 "마지막 거래일"이 미래(2026)이므로 reference date 필요
# 비교를 위해: 생존 종목의 데이터 중간 랜덤 시점을 "reference"로 삼음
# 그 reference에서 N일 전 OHLCV 측정

for i, (code, fd, ld, days) in enumerate(survivor_sample, 1):
    # 이 종목의 전체 영업일 리스트
    all_days = conn.execute("""
        SELECT date FROM daily_ohlcv_long
        WHERE code = ? ORDER BY date ASC
    """, (code,)).fetchall()
    if len(all_days) <= max(N_BEFORE) + 60:
        continue

    # 랜덤 reference date (max_N 이후 ~ 전체-1 사이)
    ref_idx = random.randint(max(N_BEFORE), len(all_days) - 1)
    ref_date = all_days[ref_idx][0]

    rows = get_nth_before(code, ref_date, max(N_BEFORE) + 1)
    if not rows:
        continue
    last_close = rows[0][1]

    for n in N_BEFORE:
        if len(rows) <= n - 1:
            continue
        d, c, v, h, l, o = rows[n]
        s = surv_agg[n]
        s['total'] += 1
        if c and c > 0:
            s['prices'].append(c)
        if v is not None:
            s['volumes'].append(v)
            if v == 0:
                s['zero_vol_count'] += 1
        if c > 0 and last_close and last_close > 0:
            s['returns_to_last'].append((last_close / c - 1) * 100)
        if c >= 1000 and v >= 50000:
            s['pass_filter'] += 1

    if i % 200 == 0:
        print(f'  생존 {i}/{len(survivor_sample)} 진행')

print(f'\n생존 종목 집계 완료')
conn.close()


# 결과 출력
print()
print('=' * 110)
print('검증 결과: 폐지 직전 N일 전 OHLCV 특성 — 자격 필터의 상폐 방어 효과')
print('=' * 110)

def report(name, agg):
    print(f'\n[{name}]')
    print(f'  {"N일전":>6} {"관측":>7} {"평균종가":>10} {"중앙종가":>10} '
          f'{"평균거래량":>12} {"중앙거래량":>12} {"거래량0":>7} {"최종대비":>9} {"필터통과":>9}')
    print('  ' + '-' * 100)
    for n in N_BEFORE:
        s = agg[n]
        if s['total'] == 0: continue
        p = np.array(s['prices']) if s['prices'] else np.array([0])
        v = np.array(s['volumes']) if s['volumes'] else np.array([0])
        r = np.array(s['returns_to_last']) if s['returns_to_last'] else np.array([0])
        zpct = s['zero_vol_count'] / s['total'] * 100
        fpct = s['pass_filter'] / s['total'] * 100
        print(f'  d-{n:>3}일  {s["total"]:>7,}  '
              f'{p.mean():>9,.0f}  {np.median(p):>9,.0f}  '
              f'{v.mean():>11,.0f}  {np.median(v):>11,.0f}  '
              f'{zpct:>6.2f}%  {r.mean():>+7.2f}%  {fpct:>7.2f}%')


report('폐지 종목 (last < 2024-06-30)', delist_agg)
report('생존 종목 (현재 거래 중)', surv_agg)

# 대조: 같은 N일에서 필터 통과율 차이
print('\n' + '=' * 90)
print('자격 필터(price>=1000 AND volume>=50000) 통과율 비교')
print('=' * 90)
print(f'{"N일전":>8} {"폐지":>12} {"생존":>12} {"폐지 제외율":>14}')
print('-' * 60)
for n in N_BEFORE:
    dp = delist_agg[n]['pass_filter'] / delist_agg[n]['total'] * 100 \
         if delist_agg[n]['total'] else 0
    sp = surv_agg[n]['pass_filter'] / surv_agg[n]['total'] * 100 \
         if surv_agg[n]['total'] else 0
    exclude_pct = 100 - dp  # 폐지 종목 제외율
    print(f'  d-{n:>3}일   {dp:>7.2f}%     {sp:>7.2f}%       {exclude_pct:>7.2f}%')

# 폐지 직전 최종 변화율 분포
print('\n' + '=' * 90)
print('폐지 종목의 "폐지 직전 가격 변화율" 분포 (N일 전 가격 → 마지막 가격)')
print('=' * 90)
for n in N_BEFORE:
    r = np.array(delist_agg[n]['returns_to_last']) if delist_agg[n]['returns_to_last'] else np.array([0])
    if len(r) > 1:
        crash_50 = (r <= -50).sum() / len(r) * 100   # 50%↓ 폭락
        crash_30 = (r <= -30).sum() / len(r) * 100
        crash_10 = (r <= -10).sum() / len(r) * 100
        print(f'  d-{n:>3}일  평균 {r.mean():>+7.2f}%  '
              f'중앙 {np.median(r):>+7.2f}%  '
              f'10%↓ {crash_10:>5.2f}%  '
              f'30%↓ {crash_30:>5.2f}%  '
              f'50%↓ {crash_50:>5.2f}%')
