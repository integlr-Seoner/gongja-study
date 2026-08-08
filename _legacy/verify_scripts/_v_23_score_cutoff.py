"""_v_23_score_cutoff.py — 종가배팅 점수 컷오프 민감도 분석

closing_bet_unified.py 의 predict() 점수 계산 이식 (뉴스 제외 80점 만점):
  차트(50): 정배열10 + 장대양봉10 + 60일신고가15 + 눌림목15
  거래대금(20): 3.0배↑20 / 2.0배↑15 / 1.5배↑10 / 1.2배↑5
  종가위치(10): ≥0.95=10 / ≥0.85=7 / ≥0.70=4

현재 등급 컷오프 (뉴스 포함 100점 만점 기준):
  HIGH ≥ 80   (뉴스 제외 환산: ≥ 60)
  MEDIUM ≥ 60 (환산: ≥ 45)
  LOW ≥ 40    (환산: ≥ 30)

측정: 5점 단위 구간별 gap_ret, realized, win rate
     + 각 컷오프 후보 (30/35/40/45/50/55/60/65/70) 적용 결과
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/4] 거래일 + 샘플 날짜...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
samples = []; cur_ym = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != cur_ym and dd >= 15:
        samples.append(d); cur_ym = ym
sample_idx_set = {date_index[d] for d in samples if d in date_index}
print(f'  샘플: {len(samples)}')

print('[2/4] OHLCV 로드...')
t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
print(f'  로드: {len(by_code_raw):,}종목, {time.time()-t0:.1f}초')

t0 = time.time()
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  numpy: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()

# -----------------------------------------------------------------------------
# 3. 점수 계산 함수 (closing_bet_unified.predict() 이식, 80점 만점)
# -----------------------------------------------------------------------------
def score_at(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    
    # ---- 차트 패턴 (50) ----
    score_chart = 0
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    # 정배열 (10점) + 장대양봉 추가 (10점)
    if (ma5 > ma10) and (ma10 > ma20):
        score_chart += 10
        body = close_t - open_t
        rng = high_t - low_t
        if rng > 0 and body > 0 and (body / rng > 0.6):
            score_chart += 10
    # 60일 신고가 (15)
    prev60_high = h[t_pos-60:t_pos].max()
    if high_t > prev60_high:
        score_chart += 15
    # 눌림목 반등 (15)
    recent_high = h[t_pos-9:t_pos+1].max()
    recent_low  = lo[t_pos-4:t_pos+1].min()
    pullback = (recent_high - recent_low) / recent_high * 100 if recent_high > 0 else 0
    today_up = close_t > c[t_pos-1]
    if (5 <= pullback <= 15) and today_up:
        score_chart += 15
    score_chart = min(50, score_chart)
    
    # ---- 거래대금 급증 (20) ----
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    score_tv = 0
    if avg20 > 0:
        ratio = today_tv / avg20
        if ratio >= 3.0: score_tv = 20
        elif ratio >= 2.0: score_tv = 15
        elif ratio >= 1.5: score_tv = 10
        elif ratio >= 1.2: score_tv = 5
    
    # ---- 종가 위치 (10) ----
    rng = high_t - low_t
    score_pos = 0
    if rng > 0:
        pos = (close_t - low_t) / rng
        if pos >= 0.95: score_pos = 10
        elif pos >= 0.85: score_pos = 7
        elif pos >= 0.70: score_pos = 4
    
    total = score_chart + score_tv + score_pos
    return {
        'gap': gap, 'total': total,
        'chart': score_chart, 'tv': score_tv, 'pos': score_pos,
    }

print('[3/4] 샘플 순회 + 점수·gap 수집...')
t0 = time.time()
# (score, gap) 튜플 누적
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        s = score_at(arr, row_pos)
        if s is None: continue
        records.append((s['total'], s['gap']))
print(f'  수집: {len(records):,}건, {time.time()-t0:.1f}초')

records_arr = np.array(records, dtype=np.float64)
scores = records_arr[:, 0]
gaps = records_arr[:, 1]

# -----------------------------------------------------------------------------
# 4. 점수 구간별 + 컷오프별 통계
# -----------------------------------------------------------------------------
print()
print('=' * 80)
print('[4/4] 점수 5점 단위 구간별 gap_ret 분포')
print('=' * 80)
print(f'{"Score":<12} {"N":>8} {"Mean%":>8} {"Median%":>8} {"Win%":>6} {"Gu5%":>6} {"Real%":>8} {"Cons%":>8}')
print('-' * 80)

for lo_s in range(0, 80, 5):
    hi_s = lo_s + 5
    mask = (scores >= lo_s) & (scores < hi_s)
    n = mask.sum()
    if n < 10:
        continue
    arr_g = gaps[mask]
    mean = arr_g.mean()
    med = np.median(arr_g)
    win = (arr_g > 0).mean() * 100
    gu5 = (arr_g >= 5).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    print(f'[{lo_s:>2}-{hi_s:>2}){"":<6} {n:>8,} {mean:>+7.3f}% {med:>+7.3f}% '
          f'{win:>5.1f}% {gu5:>5.2f}% {real:>+7.3f}% {cons:>+7.3f}%')

# 80점 만점
mask = scores >= 80
n = mask.sum()
if n >= 1:
    arr_g = gaps[mask]
    mean = arr_g.mean(); med = np.median(arr_g)
    win = (arr_g > 0).mean() * 100
    gu5 = (arr_g >= 5).mean() * 100 if n > 0 else 0
    print(f'{"[80]":<12} {n:>8,} {mean:>+7.3f}% {med:>+7.3f}% '
          f'{win:>5.1f}% {gu5:>5.2f}% {mean - ROUND_TRIP_COST_PCT:>+7.3f}% '
          f'{mean - 0.76:>+7.3f}%')

# -----------------------------------------------------------------------------
# 5. 컷오프 적용 결과 (점수 ≥ X 를 단일 필터로 썼을 때)
# -----------------------------------------------------------------------------
print()
print('=' * 80)
print('컷오프 ≥ X 적용 시 전체 수익 (단일 필터 기준)')
print('=' * 80)
print(f'{"Cutoff":<8} {"N":>8} {"Mean%":>8} {"Win%":>6} {"Gu5%":>6} {"Real%":>8} {"Cons%":>8}')
print('-' * 80)

for cutoff in [0, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]:
    mask = scores >= cutoff
    n = mask.sum()
    if n < 10:
        continue
    arr_g = gaps[mask]
    mean = arr_g.mean()
    win = (arr_g > 0).mean() * 100
    gu5 = (arr_g >= 5).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    tag = ''
    if cutoff == 30: tag = ' ← LOW 기준(80점 환산)'
    elif cutoff == 45: tag = ' ← MEDIUM 기준'
    elif cutoff == 60: tag = ' ← HIGH 기준'
    print(f'≥{cutoff:<6} {n:>8,} {mean:>+7.3f}% {win:>5.1f}% {gu5:>5.2f}% '
          f'{real:>+7.3f}% {cons:>+7.3f}%{tag}')

# -----------------------------------------------------------------------------
# 6. 최적 컷오프 판정
# -----------------------------------------------------------------------------
print()
print('=' * 80)
print('최적 컷오프 판정 (realized 양수 + N≥100)')
print('=' * 80)
best = None
for cutoff in range(0, 80, 5):
    mask = scores >= cutoff
    n = mask.sum()
    if n < 100: continue
    mean = gaps[mask].mean()
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    if real > 0:
        if best is None or (real > best['real']):
            best = {'cutoff': cutoff, 'N': n, 'mean': mean, 'real': real, 'cons': cons}
    if cutoff >= 40:
        print(f'  ≥{cutoff}: N={n:,}, realized={real:+.3f}%, conservative={cons:+.3f}%')

if best:
    print()
    print(f'최대 realized 컷오프: ≥{best["cutoff"]} (N={best["N"]:,}, realized={best["real"]:+.3f}%)')
else:
    print('  realized 양수 컷오프 없음')
print()
print('완료.')
