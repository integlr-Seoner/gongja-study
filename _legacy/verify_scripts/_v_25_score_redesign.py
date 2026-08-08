"""_v_25_score_redesign.py — 점수 시스템 재설계 시뮬레이션

_v_24 에서 밝혀진 3대 결함을 수정한 새 점수 체계 적용:
  권고 1: C3 (눌림목) 점수 15 → 5
  권고 2: 신고가+눌림목 동시 충족 시 C3 점수 무효 (모순 배제)
  권고 3: 종가 위치 배점 10 → 15

현재 점수 (80점 만점, 뉴스 제외):
  차트: 정배열10 + 장대양봉10 + 신고가15 + 눌림목15 = 50
  거래대금: 20
  종가위치: 10
  
권고 반영 점수 (80점 만점 유지):
  차트: 정배열10 + 장대양봉10 + 신고가15 + 눌림목5(모순 시 0) = 40
  거래대금: 20  
  종가위치: 15
  합계: 75 (5점 축소 - 만점 보장을 위한 재배분 고려)

대안 (80점 유지하면서 재배분):
  차트: 정배열10 + 장대양봉10 + 신고가20 + 눌림목5(모순 시 0) = 45
  거래대금: 20
  종가위치: 15
  합계: 80 ✅

이 대안으로 검증. _v_23 과 같은 5점 단위 구간별 gap_ret 측정.
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

print('[1/3] 로드...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
samples = []; cy = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        samples.append(d); cy = ym
sample_idx_set = {date_index[d] for d in samples if d in date_index}

t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  완료: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def dual_score(arr, t_pos):
    """현재 점수 + 권고 반영 새 점수 동시 계산."""
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    
    # 조건 플래그
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t; rng = high_t - low_t
    has_big = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    prev60_high = h[t_pos-60:t_pos].max()
    has_new_high = high_t > prev60_high
    recent_high = h[t_pos-9:t_pos+1].max()
    recent_low  = lo[t_pos-4:t_pos+1].min()
    pullback = (recent_high - recent_low) / recent_high * 100 if recent_high > 0 else 0
    today_up = close_t > c[t_pos-1]
    has_pullback = (5 <= pullback <= 15) and today_up
    
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    tv_ratio = today_tv / avg20 if avg20 > 0 else 0
    close_pos = (close_t - low_t) / rng if rng > 0 else 0
    
    # ---------- 현재 점수 (원본) ----------
    cur_chart = 0
    if has_align:
        cur_chart += 10
        if has_big: cur_chart += 10
    if has_new_high: cur_chart += 15
    if has_pullback: cur_chart += 15
    cur_chart = min(50, cur_chart)
    cur_tv = 0
    if tv_ratio >= 3.0: cur_tv = 20
    elif tv_ratio >= 2.0: cur_tv = 15
    elif tv_ratio >= 1.5: cur_tv = 10
    elif tv_ratio >= 1.2: cur_tv = 5
    cur_pos = 0
    if close_pos >= 0.95: cur_pos = 10
    elif close_pos >= 0.85: cur_pos = 7
    elif close_pos >= 0.70: cur_pos = 4
    cur_total = cur_chart + cur_tv + cur_pos
    
    # ---------- 권고 반영 신 점수 (80점 만점 유지) ----------
    # 차트 45 = 정배열10 + 장대양봉10 + 신고가20 + 눌림목5 (모순 시 0)
    new_chart = 0
    if has_align:
        new_chart += 10
        if has_big: new_chart += 10
    if has_new_high: new_chart += 20  # 15 → 20 (신고가 가중치 강화)
    if has_pullback and not has_new_high:
        # 모순 배제: 신고가+눌림목 동시 충족시 눌림목 무효
        new_chart += 5  # 15 → 5
    new_chart = min(45, new_chart)
    
    # 종가위치 15 = 0.95↑15 / 0.85↑10 / 0.70↑5 (가중치 상향)
    new_pos = 0
    if close_pos >= 0.95: new_pos = 15
    elif close_pos >= 0.85: new_pos = 10
    elif close_pos >= 0.70: new_pos = 5
    
    # 거래대금 20 (유지)
    new_tv = cur_tv
    
    new_total = new_chart + new_tv + new_pos
    return {
        'gap': gap,
        'cur_total': cur_total, 'new_total': new_total,
    }


print('[2/3] 점수 계산...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = dual_score(arr, row_pos)
        if r is None: continue
        records.append(r)
print(f'  수집: {len(records):,}건, {time.time()-t0:.1f}초')

arr = np.array([(r['cur_total'], r['new_total'], r['gap']) for r in records], dtype=np.float64)
cur_s = arr[:, 0]
new_s = arr[:, 1]
gaps = arr[:, 2]

# -----------------------------------------------------------------------------
# 3. 구간별 현재 vs 신 점수 비교
# -----------------------------------------------------------------------------
def interval_stats(scores, gaps, bins):
    out = []
    for lo_s, hi_s in bins:
        if hi_s is None:
            mask = scores >= lo_s
            label = f'[{lo_s}+]'
        else:
            mask = (scores >= lo_s) & (scores < hi_s)
            label = f'[{lo_s}-{hi_s})'
        n = mask.sum()
        if n < 10: continue
        g = gaps[mask]
        mean = g.mean()
        win = (g > 0).mean() * 100
        real = mean - ROUND_TRIP_COST_PCT
        out.append((label, n, mean, win, real))
    return out

print()
print('=' * 100)
print('[3/3] 현재 점수 체계 vs 권고 반영 신 체계 — 5점 단위 비교')
print('=' * 100)

bins = [(i, i+5) for i in range(30, 80, 5)] + [(80, None)]

print()
print('--- 현재 점수 체계 (80점 만점) ---')
print(f'{"구간":<10} {"N":>8} {"Mean%":>8} {"Win%":>6} {"Real%":>8}')
print('-' * 50)
for label, n, mean, win, real in interval_stats(cur_s, gaps, bins):
    print(f'{label:<10} {n:>8,} {mean:>+7.3f}% {win:>5.1f}% {real:>+7.3f}%')

print()
print('--- 권고 반영 신 체계 (80점 만점 유지) ---')
print(f'{"구간":<10} {"N":>8} {"Mean%":>8} {"Win%":>6} {"Real%":>8}')
print('-' * 50)
for label, n, mean, win, real in interval_stats(new_s, gaps, bins):
    print(f'{label:<10} {n:>8,} {mean:>+7.3f}% {win:>5.1f}% {real:>+7.3f}%')


# -----------------------------------------------------------------------------
# 4. 컷오프 비교
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('컷오프 ≥ X 적용 시 realized 비교')
print('=' * 100)
print(f'{"컷오프":<8} {"현재 N":>8} {"현재 real%":>12} | {"신 N":>8} {"신 real%":>12} | {"차이 real%":>12}')
print('-' * 100)

for cutoff in [30, 35, 40, 45, 50, 55, 60, 65, 70]:
    cur_mask = cur_s >= cutoff
    new_mask = new_s >= cutoff
    cur_n = cur_mask.sum()
    new_n = new_mask.sum()
    if cur_n < 10 and new_n < 10: continue
    cur_real = gaps[cur_mask].mean() - ROUND_TRIP_COST_PCT if cur_n > 0 else 0
    new_real = gaps[new_mask].mean() - ROUND_TRIP_COST_PCT if new_n > 0 else 0
    diff = new_real - cur_real
    print(f'≥{cutoff:<6} {cur_n:>8,} {cur_real:>+11.3f}% | {new_n:>8,} {new_real:>+11.3f}% | {diff:>+11.3f}%p')

# -----------------------------------------------------------------------------
# 5. 단조 증가성 테스트 (점수가 높을수록 realized 도 단조 증가하는가?)
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('단조 증가성 — 점수 구간별 realized 증감')
print('=' * 100)

def check_monotonic(scores, gaps, name):
    bins_small = [(i, i+5) for i in range(30, 80, 5)]
    reals = []
    labels = []
    for lo_s, hi_s in bins_small:
        mask = (scores >= lo_s) & (scores < hi_s)
        n = mask.sum()
        if n < 50: 
            reals.append(None); labels.append(f'[{lo_s}-{hi_s})')
            continue
        reals.append(gaps[mask].mean() - ROUND_TRIP_COST_PCT)
        labels.append(f'[{lo_s}-{hi_s})')
    
    print(f'\n{name}:')
    print(f'  {"구간":<10} {"realized":>10}  {"증감":>8}')
    prev = None
    inversions = 0
    for label, real in zip(labels, reals):
        if real is None:
            print(f'  {label:<10} {"N/A":>10}')
            continue
        delta = real - prev if prev is not None else None
        mark = ''
        if delta is not None:
            if delta < -0.1:
                mark = ' ← 역전'
                inversions += 1
            elif delta < 0:
                mark = ' (소폭 하락)'
        print(f'  {label:<10} {real:>+9.3f}%  {(f"{delta:>+7.3f}%" if delta is not None else "  -"):>8}{mark}')
        prev = real
    print(f'  → 역전(Δ < -0.1%) 횟수: {inversions}')

check_monotonic(cur_s, gaps, '현재 체계')
check_monotonic(new_s, gaps, '권고 반영 체계')

print()
print('완료.')
