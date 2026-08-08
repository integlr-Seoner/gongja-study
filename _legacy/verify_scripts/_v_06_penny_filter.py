"""검증: MIN_PRICE=1000 동전주 필터의 자격 필터 타당성
근본적 원칙:
  - 수익률이 아닌 위험 지표를 측정
  - 가격 구간별 위험이 체계적으로 다른지 확인
  - 다르다면 MIN_PRICE=1000은 자격 필터로 유효
  - 비슷하다면 근거 없는 임의 기준

가격 구간: <500, 500-999, 1000-1999, 2000-4999, 5000+

실측 지표 (T = 샘플 날짜):
  A. 상폐율: T+120 영업일 이후 데이터 없음
  B. 극단 하락: T+1~T+20 내 close가 T종가의 -30%↓ 달성
  C. 20일 변동성: T+1~T+20 일일 수익률 표준편차 평균
  D. 거래정지: T+1~T+20 내 volume=0 발생 (OHL 이상 포함)

샘플: 2014-01 ~ 2023-12 월 단위 중순 (120영업일 추적 가능)
"""
import sqlite3
import numpy as np
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
conn = sqlite3.connect(DB, timeout=30)

# 샘플 날짜 수집
all_dates = [r[0] for r in conn.execute("""
    SELECT DISTINCT date FROM daily_ohlcv_long
    WHERE date >= '20140101' AND date <= '20231231'
    ORDER BY date
""").fetchall()]

samples = []
current_ym = ''
for d in all_dates:
    ym = d[:6]
    dd = int(d[6:8])
    if ym != current_ym and dd >= 15:
        samples.append(d)
        current_ym = ym

print(f'샘플 날짜: {len(samples)}개 (2014-01~2023-12 월 단위 중순)')
print(f'추적 기간: T+1 ~ T+120 영업일')
print()


def get_future_dates(asof, n):
    """asof 이후 n영업일까지 날짜 리스트"""
    r = conn.execute("""
        SELECT DISTINCT date FROM daily_ohlcv_long
        WHERE date > ? ORDER BY date ASC LIMIT ?
    """, (asof, n)).fetchall()
    return [x[0] for x in r]


def classify_price(p):
    if p < 500: return '<500'
    if p < 1000: return '500-999'
    if p < 2000: return '1000-1999'
    if p < 5000: return '2000-4999'
    return '5000+'


buckets = ['<500', '500-999', '1000-1999', '2000-4999', '5000+']
# {bucket: {'total': n, 'delisted': n, 'crash30': n, 'vols': [],
#           'stop_days': n, 'total_days': n}}
agg = {b: {'total': 0, 'delisted': 0, 'crash30': 0,
           'vols': [], 'stop_days': 0, 'total_days': 0} for b in buckets}

for i, asof in enumerate(samples, 1):
    today = conn.execute("""
        SELECT code, close FROM daily_ohlcv_long
        WHERE date = ? AND close > 0
          AND close BETWEEN low AND high
    """, (asof,)).fetchall()
    if not today:
        continue

    # T+1~T+20 데이터 한 번에 로드
    future_20 = get_future_dates(asof, 20)
    if len(future_20) < 20:
        continue
    last_20 = future_20[-1]

    # T+120 날짜
    future_120 = get_future_dates(asof, 120)
    t120 = future_120[-1] if len(future_120) >= 120 else None

    codes = [c for c, _ in today]
    code_price = {c: p for c, p in today}

    # 한 번에 T+1~T+20 범위 OHLCV 로드
    ph = ','.join('?' * len(codes))
    rows_fut = conn.execute(f"""
        SELECT code, date, open, high, low, close, volume
        FROM daily_ohlcv_long
        WHERE code IN ({ph}) AND date > ? AND date <= ?
    """, codes + [asof, last_20]).fetchall()

    # 종목별 미래 데이터 모음
    fut_by_code = defaultdict(list)
    for code, d, o, h, l, c, v in rows_fut:
        fut_by_code[code].append((d, o, h, l, c, v))

    # T+120 존재 여부 (상폐 판정)
    exists_120 = set()
    if t120:
        t120_rows = conn.execute(f"""
            SELECT DISTINCT code FROM daily_ohlcv_long
            WHERE code IN ({ph}) AND date > ? AND date <= ?
        """, codes + [last_20, t120]).fetchall()
        exists_120 = {x[0] for x in t120_rows}

    for code, p0 in today:
        bucket = classify_price(p0)
        a = agg[bucket]
        a['total'] += 1

        # A. 상폐 판정
        # 샘플 날짜가 T+120까지 추적 가능할 때만 집계
        if t120 is not None:
            if code not in exists_120:
                a['delisted'] += 1

        fut = fut_by_code.get(code, [])
        if not fut:
            continue

        # B. 극단 하락 -30%↓ (T+1 ~ T+20 내 최저가 기준)
        lows_20 = [l for d, o, h, l, c, v in fut[:20] if l > 0]
        if lows_20 and p0 > 0:
            min_low = min(lows_20)
            dd = (min_low / p0 - 1) * 100
            if dd <= -30:
                a['crash30'] += 1

        # C. 20일 변동성 (일일 종가 기준 수익률 std)
        closes = [c for d, o, h, l, c, v in fut[:20] if c > 0]
        if len(closes) >= 5:
            prev = p0
            rets = []
            for c in closes:
                if prev > 0:
                    rets.append((c / prev - 1) * 100)
                prev = c
            if len(rets) >= 5:
                a['vols'].append(np.std(rets))

        # D. 거래정지 일수 (volume=0 또는 OHL 이상)
        for d, o, h, l, c, v in fut[:20]:
            a['total_days'] += 1
            if v == 0 or (o == h == l == c and v == 0):
                a['stop_days'] += 1

    if i % 12 == 0:
        print(f'  {i}/{len(samples)}')

conn.close()


print()
print('=' * 100)
print('검증 결과: 가격 구간별 위험 지표 (샘플 N=영업일 × 종목-날짜 조합)')
print('=' * 100)
print(f'{"구간":<11} {"관측":>10} {"상폐율":>9} {"극단하락":>9} {"20d변동성":>11} {"거래정지":>9}')
print(f'{"":11} {"(종목-일)":>10} {"120d":>9} {"(-30%↓)":>9} {"(일수익%/σ)":>11} {"(vol=0)":>9}')
print('-' * 100)

for b in buckets:
    a = agg[b]
    if a['total'] == 0:
        print(f'  {b:<11} 데이터 없음')
        continue
    delist_pct = a['delisted'] / a['total'] * 100
    crash_pct = a['crash30'] / a['total'] * 100
    vol_avg = np.mean(a['vols']) if a['vols'] else 0
    stop_pct = a['stop_days'] / a['total_days'] * 100 if a['total_days'] else 0
    print(f'  {b:<11} {a["total"]:>10,} '
          f'{delist_pct:>7.2f}%  '
          f'{crash_pct:>7.2f}%  '
          f'{vol_avg:>9.3f}  '
          f'{stop_pct:>7.3f}%')

# 컷오프 비교: <1000 vs >=1000
under = {'total': 0, 'delisted': 0, 'crash30': 0, 'vols': [],
         'stop_days': 0, 'total_days': 0}
over = {'total': 0, 'delisted': 0, 'crash30': 0, 'vols': [],
        'stop_days': 0, 'total_days': 0}
for b in ['<500', '500-999']:
    for k in ['total', 'delisted', 'crash30', 'stop_days', 'total_days']:
        under[k] += agg[b][k]
    under['vols'].extend(agg[b]['vols'])
for b in ['1000-1999', '2000-4999', '5000+']:
    for k in ['total', 'delisted', 'crash30', 'stop_days', 'total_days']:
        over[k] += agg[b][k]
    over['vols'].extend(agg[b]['vols'])

print()
print('=' * 100)
print('MIN_PRICE=1000 컷오프 기준 비교')
print('=' * 100)
print(f'{"구간":<12} {"관측":>10} {"상폐율":>10} {"극단하락":>10} {"변동성":>10} {"거래정지":>10}')
print('-' * 80)

for lbl, a in [('<1000 (제외)', under), ('>=1000 (통과)', over)]:
    if a['total'] == 0: continue
    d = a['delisted'] / a['total'] * 100
    c = a['crash30'] / a['total'] * 100
    v = np.mean(a['vols']) if a['vols'] else 0
    s = a['stop_days'] / a['total_days'] * 100 if a['total_days'] else 0
    print(f'  {lbl:<12} {a["total"]:>10,} '
          f'{d:>8.2f}%   {c:>8.2f}%   {v:>8.3f}   {s:>8.3f}%')

# 배율
if over['total'] and under['total']:
    r_d = (under['delisted']/under['total']) / max((over['delisted']/over['total']), 1e-9)
    r_c = (under['crash30']/under['total']) / max((over['crash30']/over['total']), 1e-9)
    r_v = (np.mean(under['vols']) if under['vols'] else 0) / max((np.mean(over['vols']) if over['vols'] else 1e-9), 1e-9)
    print(f'\n배율 (<1000 / >=1000):')
    print(f'  상폐율     {r_d:.2f}배')
    print(f'  극단하락   {r_c:.2f}배')
    print(f'  변동성     {r_v:.2f}배')
