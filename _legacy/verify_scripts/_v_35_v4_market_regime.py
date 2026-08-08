"""_v_35_v4_market_regime.py — V4 시그널 × 시장 레짐 교차 분석

배경:
  V4는 실전 1개월에서 CAGR +120% 를 보였지만 2026-03~04는 강세장 가능성.
  V4가 강세장/횡보/약세장 각각에서 어떻게 작동하는지 검증해야 운영 안전성 판단 가능.

레짐 분류:
  KOSPI 20일 수익률 기준
    BULL     >= +5%
    SIDEWAYS -5% ~ +5%
    BEAR     <= -5%

측정:
  ① 각 레짐에서 V4 score==4 분포, realized, 승률
  ② 레짐 전환기 (BULL → BEAR 시점) 의 V4 성과
  ③ 최악 레짐(BEAR) 에서도 운영 가능한지
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict, Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

REGIME_BULL_THRESHOLD = 5.0   # KOSPI 20d >= +5%
REGIME_BEAR_THRESHOLD = -5.0  # KOSPI 20d <= -5%


def classify_regime(kospi_ret_20d):
    if kospi_ret_20d >= REGIME_BULL_THRESHOLD: return 'BULL'
    elif kospi_ret_20d <= REGIME_BEAR_THRESHOLD: return 'BEAR'
    else: return 'SIDEWAYS'


conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/4] KOSPI 지수 로드 + 레짐 분류...')
kospi_rows = cur.execute(
    "SELECT date, close FROM daily_index_long "
    "WHERE symbol='KOSPI' AND date >= '20140101' ORDER BY date"
).fetchall()
kospi_dates = [r[0] for r in kospi_rows]
kospi_closes = np.array([r[1] for r in kospi_rows])
print(f'  KOSPI: {len(kospi_dates):,}일, {kospi_dates[0]} ~ {kospi_dates[-1]}')

# 날짜별 KOSPI 20일 수익률 + 레짐
date_to_regime = {}
date_to_ret20 = {}
for i in range(20, len(kospi_dates)):
    ret20 = (kospi_closes[i] / kospi_closes[i-20] - 1) * 100
    date_to_regime[kospi_dates[i]] = classify_regime(ret20)
    date_to_ret20[kospi_dates[i]] = ret20

# 레짐 분포 확인
print(f'\n  레짐 분포 (전체 거래일):')
regime_count = Counter(date_to_regime.values())
for rg, n in regime_count.most_common():
    print(f'    {rg:<10}: {n:,}일 ({n/len(date_to_regime)*100:.1f}%)')

print('\n[2/4] 거래일 + 샘플...')
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

print('[3/4] OHLCV 로드...')
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
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def v4_at(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t; rng = high_t - low_t
    cond1 = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    cond2 = high_t > h[t_pos-60:t_pos].max()
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    cond3 = (avg20 > 0) and (today_tv / avg20 >= 3.0)
    cond4 = (rng > 0) and ((close_t - low_t) / rng >= 0.95)
    score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    return {'gap': gap, 'score': score}


print('[4/4] V4 × 레짐 교차 측정...')
t0 = time.time()
# records: (score, gap, date, regime)
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = v4_at(arr, row_pos)
        if r is None: continue
        date_str = all_dates[date_idx]
        regime = date_to_regime.get(date_str)
        if regime is None: continue
        records.append((r['score'], r['gap'], date_str, regime))
print(f'  완료: {len(records):,}건, {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 분석 1: 레짐 × score 매트릭스
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('[결과] 레짐 × V4 score 교차 매트릭스')
print('=' * 100)
REGIMES = ['BULL', 'SIDEWAYS', 'BEAR']

# 레짐별 샘플 수
sample_regime = Counter(r[3] for r in records)
print(f'\n  각 레짐의 관측치 수:')
for rg in REGIMES:
    print(f'    {rg:<10}: {sample_regime.get(rg, 0):,}건 ({sample_regime.get(rg, 0)/len(records)*100:.1f}%)')

# 매트릭스
print()
print(f'{"score":<8}', end='')
for rg in REGIMES:
    print(f' {rg+"_N":>10} {rg+"_mean":>11} {rg+"_real":>11} {rg+"_win":>9}', end='')
print()
print('-' * 125)

matrix = {}
for s in range(5):
    print(f'{s:<8}', end='')
    for rg in REGIMES:
        gaps = [g for sc, g, _, r in records if sc == s and r == rg]
        if len(gaps) < 5:
            print(f' {len(gaps):>10} {"-":>11} {"-":>11} {"-":>9}', end='')
            continue
        arr = np.array(gaps)
        mean = arr.mean()
        real = mean - ROUND_TRIP_COST_PCT
        win = (arr > 0).mean() * 100
        matrix[(s, rg)] = {'n': len(arr), 'mean': mean, 'real': real, 'win': win}
        print(f' {len(gaps):>10,} {mean:>+10.3f}% {real:>+10.3f}% {win:>8.1f}%', end='')
    print()

# -----------------------------------------------------------------------------
# 분석 2: score==4 의 레짐별 상세
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('score==4 레짐별 상세')
print('=' * 100)
print(f'{"레짐":<12} {"N":>6} {"mean":>9} {"승률":>8} {"갭5%↑":>8} {"realized":>10} {"conservative":>13}')
print('-' * 100)
for rg in REGIMES:
    gaps = [g for sc, g, _, r in records if sc == 4 and r == rg]
    if not gaps: continue
    arr = np.array(gaps)
    mean = arr.mean()
    win = (arr > 0).mean() * 100
    gu5 = (arr >= 5).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    print(f'{rg:<12} {len(arr):>6,} {mean:>+8.3f}% '
          f'{win:>7.1f}% {gu5:>7.1f}% {real:>+9.3f}% {cons:>+12.3f}%')

# 최저 레짐 대비 최고 레짐 비율
if all((4, rg) in matrix for rg in REGIMES):
    best = max(matrix[(4, rg)]['real'] for rg in REGIMES)
    worst = min(matrix[(4, rg)]['real'] for rg in REGIMES)
    print(f'\n  레짐 격차: 최고 {best:+.3f}% / 최저 {worst:+.3f}% (차이 {best-worst:.3f}%p)')


# -----------------------------------------------------------------------------
# 분석 3: 레짐 전환기 (전환 직전 20일)
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('레짐 전환기 분석 — 전환 직전 5영업일')
print('=' * 100)

# 레짐 전환 시점 찾기
sorted_dates = sorted(date_to_regime.keys())
transitions = []  # (date, from, to)
for i in range(1, len(sorted_dates)):
    prev = date_to_regime[sorted_dates[i-1]]
    curr = date_to_regime[sorted_dates[i]]
    if prev != curr:
        transitions.append((sorted_dates[i], prev, curr))
print(f'\n  총 {len(transitions)}회 레짐 전환 발생')

# BULL→BEAR 전환 직전 5일의 V4 성과
bull_to_bear = [t for t in transitions if t[1] == 'BULL' and t[2] == 'BEAR']
bear_to_bull = [t for t in transitions if t[1] == 'BEAR' and t[2] == 'BULL']
print(f'  BULL→BEAR 전환: {len(bull_to_bear)}회')
print(f'  BEAR→BULL 전환: {len(bear_to_bull)}회')

def pre_transition_performance(transitions_list, days_before=5):
    """전환 직전 N일의 score==4 gap 모으기"""
    pre_gaps = []
    pre_all_gaps = []
    for trans_date, _, _ in transitions_list:
        # 전환 직전 N일 찾기
        if trans_date not in date_index: continue
        t_idx = date_index[trans_date]
        for back in range(1, days_before + 1):
            if t_idx - back < 0: continue
            target_date = all_dates[t_idx - back]
            for sc, g, d, _ in records:
                if d == target_date:
                    pre_all_gaps.append(g)
                    if sc == 4:
                        pre_gaps.append(g)
    return pre_gaps, pre_all_gaps

pre_bb, pre_all_bb = pre_transition_performance(bull_to_bear)
pre_bbull, pre_all_bbull = pre_transition_performance(bear_to_bull)

print(f'\n  BULL→BEAR 전환 직전 5일 성과:')
if pre_bb:
    a = np.array(pre_bb)
    print(f'    V4=4: N={len(a)}, mean={a.mean():+.3f}%, '
          f'real={a.mean()-ROUND_TRIP_COST_PCT:+.3f}%, win={(a>0).mean()*100:.1f}%')
else:
    print(f'    V4=4: N=0')

print(f'\n  BEAR→BULL 전환 직전 5일 성과:')
if pre_bbull:
    a = np.array(pre_bbull)
    print(f'    V4=4: N={len(a)}, mean={a.mean():+.3f}%, '
          f'real={a.mean()-ROUND_TRIP_COST_PCT:+.3f}%, win={(a>0).mean()*100:.1f}%')

# -----------------------------------------------------------------------------
# 분석 4: 운영 권고 (레짐별)
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('운영 권고 (레짐별 V4 채택 결정)')
print('=' * 100)
for rg in REGIMES:
    if (4, rg) in matrix:
        m = matrix[(4, rg)]
        status = '✅ 채택' if m['real'] > 1.0 else '⚠ 주의' if m['real'] > 0 else '❌ 회피'
        print(f'  {rg:<10}: N={m["n"]:>5}, realized={m["real"]:+.3f}%, win={m["win"]:.1f}% → {status}')

print()
print('완료.')
