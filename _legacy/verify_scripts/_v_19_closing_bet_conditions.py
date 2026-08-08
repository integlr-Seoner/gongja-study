"""_v_19_closing_bet_conditions.py — 종가배팅 4조건 gap_ret 검증 (v2 최적화)

v1 성능 문제: 148 샘플 × 90일 × 수천종목 SQL 재조회 → 타임아웃
v2 전략: 전체 OHLCV (8.3M 행) 메모리 로드 후 종목별 numpy 배열 구성 → 인덱싱만

종가배팅 조건 (closing_bet_unified.py 실측 정의):
  C1  정배열+장대양봉  (MA5>MA10>MA20 AND body/range > 0.6)
  C2  60일 신고가       (high[T] > max(high[T-60..T-1]))
  C3  눌림목 후 반등    (recent10일 range=5~15% AND 오늘 양봉)
  V   거래대금 급증     (전20일 평균의 1.5배↑)
  P   종가 위치 상단    ((close-low)/(high-low) >= 0.7)

비교: _v_13 베이스라인 +0.147%, 자격 +0.189%
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46
BASELINE_MEAN = 0.147
QUALIFY_MEAN  = 0.189

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# -----------------------------------------------------------------------------
# 1. 샘플 날짜 추출 (월 1회, 15일 이후 첫 영업일)
# -----------------------------------------------------------------------------
print('[1/4] 샘플 날짜 추출...')
all_dates = [r[0] for r in cur.execute("""
    SELECT DISTINCT date FROM daily_ohlcv_long
    WHERE date >= '20140101' AND date <= '20260417'
    ORDER BY date
""").fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}

samples = []
current_ym = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != current_ym and dd >= 15:
        samples.append(d)
        current_ym = ym
print(f'  샘플 날짜: {len(samples)}개, 전체 거래일: {len(all_dates)}개')

# -----------------------------------------------------------------------------
# 2. 보통주 코드 집합 (끝자리 0 필터)
# -----------------------------------------------------------------------------
print('[2/4] 보통주 코드 추출...')
all_codes = [r[0] for r in cur.execute(
    "SELECT DISTINCT code FROM daily_ohlcv_long WHERE substr(code, -1) = '0'"
).fetchall()]
print(f'  보통주 코드: {len(all_codes):,}개')

# -----------------------------------------------------------------------------
# 3. 전체 OHLCV 메모리 로드 (종목별 numpy 배열)
# -----------------------------------------------------------------------------
print('[3/4] OHLCV 전체 로드 중... (약 8.3M 행)')
t0 = time.time()
# 종목별로 (date_idx, o, h, l, c, v) 튜플 수집
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None:
        continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
print(f'  로드 완료: {len(by_code_raw):,}개 종목, {time.time()-t0:.1f}초')

# numpy 배열 변환
t0 = time.time()
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61:  # C2 의 60일 신고가 계산 최소 요건
        continue
    arr = np.array(rows, dtype=np.float64)
    by_code[code] = arr  # shape (n, 6): [idx, o, h, l, c, v]
del by_code_raw
print(f'  numpy 변환: {len(by_code):,}개 종목 (61일 이상), {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 4. 샘플 날짜별 조건 계산 + gap_ret 수집
# -----------------------------------------------------------------------------

GROUPS = {
    'C1_정배열_장대양봉':  lambda f: f['C1'],
    'C2_60일신고가':        lambda f: f['C2'],
    'C3_눌림목반등':        lambda f: f['C3'],
    'V_거래대금급증':       lambda f: f['V'],
    'P_종가위치상단':       lambda f: f['P'],
    'C1+V':                 lambda f: f['C1'] and f['V'],
    'C2+V':                 lambda f: f['C2'] and f['V'],
    'C2+V+P':               lambda f: f['C2'] and f['V'] and f['P'],
    'C1+V+P':               lambda f: f['C1'] and f['V'] and f['P'],
    'C1+C2+V':              lambda f: f['C1'] and f['C2'] and f['V'],
}
results = {name: [] for name in GROUPS}

def calc_at(arr: np.ndarray, t_pos: int) -> dict:
    """arr[t_pos] = T일. arr[t_pos+1] = T+1일 (gap_ret용).
    t_pos 는 배열 안 T일의 인덱스. 최소 60일 이전 데이터 있어야.
    """
    if t_pos < 60 or t_pos + 1 >= len(arr):
        return None
    
    # T+1 의 실제 날짜가 T 바로 다음 영업일이어야 (연속성 확인)
    next_date_idx = int(arr[t_pos + 1, 0])
    curr_date_idx = int(arr[t_pos, 0])
    if next_date_idx != curr_date_idx + 1:
        return None
    
    o = arr[:, 1]; h = arr[:, 2]; lo = arr[:, 3]; c = arr[:, 4]; v = arr[:, 5]
    open_t  = o[t_pos];  high_t = h[t_pos]
    low_t   = lo[t_pos]; close_t = c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos + 1]
    
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    
    gap = (open_t1 / close_t - 1) * 100
    
    # C1: 정배열 + 장대양봉
    ma5  = c[t_pos - 4:t_pos + 1].mean()
    ma10 = c[t_pos - 9:t_pos + 1].mean()
    ma20 = c[t_pos - 19:t_pos + 1].mean()
    C1_order = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t  # 오늘의 시가 대비 종가
    rng = high_t - low_t
    C1_big = (rng > 0) and (body > 0) and (body / rng > 0.6)
    C1 = C1_order and C1_big
    
    # C2: 60일 신고가
    prev60_high = h[t_pos - 60:t_pos].max()
    C2 = high_t > prev60_high
    
    # C3: 눌림목 후 반등
    recent_high = h[t_pos - 9:t_pos + 1].max()
    recent_low  = lo[t_pos - 4:t_pos + 1].min()
    pullback = (recent_high - recent_low) / recent_high * 100 if recent_high > 0 else 0
    today_up = close_t > c[t_pos - 1]
    C3 = (5 <= pullback <= 15) and today_up
    
    # V: 거래대금 급증
    tv = c[t_pos - 20:t_pos] * v[t_pos - 20:t_pos]
    avg20 = tv.mean()
    today_tv = close_t * vol_t
    V = (avg20 > 0) and (today_tv / avg20 >= 1.5)
    
    # P: 종가 위치 상단
    P = (rng > 0) and ((close_t - low_t) / rng >= 0.70)
    
    return {'gap': gap, 'C1': C1, 'C2': C2, 'C3': C3, 'V': V, 'P': P}

print('[4/4] 샘플 순회 + 조건 계산...')
t0 = time.time()
sample_idx_set = {date_index[d] for d in samples if d in date_index}

for code, arr in by_code.items():
    # 이 종목 배열에서 샘플 날짜 위치 찾기
    dates_col = arr[:, 0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set:
            continue
        f = calc_at(arr, row_pos)
        if f is None:
            continue
        gap = f['gap']
        for name, fn in GROUPS.items():
            if fn(f):
                results[name].append(gap)

print(f'  조건 계산 완료: {time.time()-t0:.1f}초')
print()
for name, arr in results.items():
    print(f'  {name:30s} N={len(arr):,}')
print()

# -----------------------------------------------------------------------------
# 통계 출력
# -----------------------------------------------------------------------------
print('=' * 110)
print(f'{"Group":<30} {"N":>8} {"Mean%":>8} {"Win%":>6} {"Gu5%":>6} {"Real":>8} {"Cons":>8} {"Δ base":>9} {"Δ qual":>9}')
print('-' * 110)

rows = []
for name, arr in results.items():
    if not arr:
        continue
    a = np.array(arr)
    n = len(a)
    mean = a.mean()
    win = (a > 0).mean() * 100
    gu5 = (a >= 5).mean() * 100
    realized = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    dbase = mean - BASELINE_MEAN
    dqual = mean - QUALIFY_MEAN
    rows.append({'name': name, 'N': n, 'mean': mean, 'win': win,
                 'gu5': gu5, 'realized': realized, 'cons': cons,
                 'dbase': dbase, 'dqual': dqual})
    print(f'{name:<30} {n:>8,} {mean:>+7.3f}% {win:>5.1f}% {gu5:>5.2f}% '
          f'{realized:>+7.3f}% {cons:>+7.3f}% {dbase:>+8.3f}p {dqual:>+8.3f}p')

print()
print('=' * 110)
print('판정 — realized 양수 그룹 (수수료 0.46% 차감 후)')
print('=' * 110)
pos = [r for r in rows if r['realized'] > 0 and r['N'] >= 100]
if pos:
    for r in sorted(pos, key=lambda x: -x['realized']):
        print(f'  {r["name"]:<30}  realized={r["realized"]:+.3f}%  N={r["N"]:,}')
else:
    print('  없음.')
print()
print('완료.')
conn.close()
