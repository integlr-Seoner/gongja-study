"""_v_24_overheated_analysis.py — 70점+ OVERHEATED 역전 원인 분석

배경: _v_23 에서 65~70점 realized +2.120% (최강) → 70~75점 -0.158% 로 급락.
목적: 이 비선형 역전의 원인 규명.

가설:
  A. 과열 후 차익실현 — 70점+ T일 등락률이 65-70보다 훨씬 높음?
  B. 상한가 근접 매수 후 갭하락 — 70점+ 중 T일 +15%↑ 비율?
  C. 특정 조건 조합의 독성 — 어떤 조건이 70점대를 만드는지?
  D. 소형주 편향 — 70점+ 거래대금 분포?
  E. 샘플 부족·시기 편향 — 연도별 realized 일관성?
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
sample_idx_to_date = {date_index[d]: d for d in samples if d in date_index}

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

by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  완료: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()

# -----------------------------------------------------------------------------
# 점수 + 풍부한 메타데이터 수집 (65점+ 만)
# -----------------------------------------------------------------------------
def deep_score(arr, t_pos, date_str):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    
    # 점수 계산 (_v_23과 동일)
    s_chart = 0
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    has_big = False
    if has_align:
        s_chart += 10
        body = close_t - open_t; rng = high_t - low_t
        if rng > 0 and body > 0 and (body / rng > 0.6):
            s_chart += 10
            has_big = True
    prev60_high = h[t_pos-60:t_pos].max()
    has_new_high = high_t > prev60_high
    if has_new_high: s_chart += 15
    recent_high = h[t_pos-9:t_pos+1].max()
    recent_low  = lo[t_pos-4:t_pos+1].min()
    pullback = (recent_high - recent_low) / recent_high * 100 if recent_high > 0 else 0
    today_up = close_t > c[t_pos-1]
    has_pullback = (5 <= pullback <= 15) and today_up
    if has_pullback: s_chart += 15
    s_chart = min(50, s_chart)
    
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    tv_ratio = today_tv / avg20 if avg20 > 0 else 0
    s_tv = 0
    if tv_ratio >= 3.0: s_tv = 20
    elif tv_ratio >= 2.0: s_tv = 15
    elif tv_ratio >= 1.5: s_tv = 10
    elif tv_ratio >= 1.2: s_tv = 5
    
    rng = high_t - low_t
    close_pos = (close_t - low_t) / rng if rng > 0 else 0
    s_pos = 0
    if close_pos >= 0.95: s_pos = 10
    elif close_pos >= 0.85: s_pos = 7
    elif close_pos >= 0.70: s_pos = 4
    
    total = s_chart + s_tv + s_pos
    
    # T일 등락률 (전일 close 대비)
    prev_close = c[t_pos - 1]
    day_change = (close_t / prev_close - 1) * 100 if prev_close > 0 else 0
    
    return {
        'date': date_str, 'total': total, 'gap': gap,
        'chart': s_chart, 'tv': s_tv, 'pos': s_pos,
        'tv_ratio': tv_ratio, 'close_pos': close_pos,
        'day_change': day_change, 'close_t': close_t, 'vol_t': vol_t,
        'today_tv_won': today_tv,  # 거래대금 (원)
        'has_align': has_align, 'has_big': has_big,
        'has_new_high': has_new_high, 'has_pullback': has_pullback,
    }

print('[3/4] 샘플 순회 (65점+ 저장)...')
t0 = time.time()
records = []  # 점수 45+ 만 저장 (메모리 절약)
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = deep_score(arr, row_pos, sample_idx_to_date[date_idx])
        if r is None: continue
        if r['total'] >= 45:
            records.append(r)
print(f'  수집: {len(records):,}건, {time.time()-t0:.1f}초')
print()

# 그룹 분할
g_45_50 = [r for r in records if 45 <= r['total'] < 50]
g_50_55 = [r for r in records if 50 <= r['total'] < 55]
g_55_60 = [r for r in records if 55 <= r['total'] < 60]
g_60_65 = [r for r in records if 60 <= r['total'] < 65]
g_65_70 = [r for r in records if 65 <= r['total'] < 70]  # sweet spot
g_70_75 = [r for r in records if 70 <= r['total'] < 75]  # 역전 시작
g_75_80 = [r for r in records if 75 <= r['total'] < 80]
g_80    = [r for r in records if r['total'] >= 80]

groups = [
    ('[50-55)', g_50_55), ('[55-60)', g_55_60), ('[60-65)', g_60_65),
    ('[65-70)', g_65_70), ('[70-75)', g_70_75), ('[75-80)', g_75_80),
    ('[80+]',   g_80),
]

def stats(g):
    if not g: return None
    gaps = np.array([r['gap'] for r in g])
    day_chs = np.array([r['day_change'] for r in g])
    tv_rs = np.array([r['tv_ratio'] for r in g])
    poses = np.array([r['close_pos'] for r in g])
    tv_wons = np.array([r['today_tv_won'] for r in g])
    return {
        'N': len(g),
        'mean_gap': gaps.mean(),
        'realized': gaps.mean() - ROUND_TRIP_COST_PCT,
        # T일 당일 등락률 분포
        'day_chg_mean': day_chs.mean(),
        'day_chg_p50': np.percentile(day_chs, 50),
        'day_chg_p90': np.percentile(day_chs, 90),
        'day_chg_15pct': (day_chs >= 15).mean() * 100,
        'day_chg_10pct': (day_chs >= 10).mean() * 100,
        'day_chg_5pct':  (day_chs >= 5).mean() * 100,
        # 거래대금 비율
        'tv_ratio_mean': tv_rs.mean(),
        'tv_ratio_p50': np.percentile(tv_rs, 50),
        'tv_ratio_3x': (tv_rs >= 3).mean() * 100,
        # 종가위치
        'pos_p50': np.percentile(poses, 50),
        'pos_95': (poses >= 0.95).mean() * 100,
        # 거래대금(원) 분포 — 중위수, 5분위
        'tv_won_p20': np.percentile(tv_wons, 20) / 1e8,  # 억원
        'tv_won_p50': np.percentile(tv_wons, 50) / 1e8,
        'tv_won_p80': np.percentile(tv_wons, 80) / 1e8,
        # 조건 충족 비율
        'pct_align':      sum(r['has_align']      for r in g) / len(g) * 100,
        'pct_big':        sum(r['has_big']        for r in g) / len(g) * 100,
        'pct_new_high':   sum(r['has_new_high']   for r in g) / len(g) * 100,
        'pct_pullback':   sum(r['has_pullback']   for r in g) / len(g) * 100,
    }

print('=' * 120)
print('[가설 A/D] T일 당일 등락률 + 거래대금 규모 분석')
print('=' * 120)
print(f'{"그룹":<10} {"N":>6} {"Real%":>7} | {"T일변동":>8} {"T일 p50":>8} {"T일 p90":>8} {"≥15%":>6} {"≥10%":>6} {"≥5%":>6} | {"TV억 p20":>9} {"p50":>9} {"p80":>9}')
print('-' * 120)
for name, g in groups:
    s = stats(g)
    if not s: continue
    print(f'{name:<10} {s["N"]:>6,} {s["realized"]:>+6.2f}% | '
          f'{s["day_chg_mean"]:>+7.2f}% {s["day_chg_p50"]:>+7.2f}% {s["day_chg_p90"]:>+7.2f}% '
          f'{s["day_chg_15pct"]:>5.1f}% {s["day_chg_10pct"]:>5.1f}% {s["day_chg_5pct"]:>5.1f}% | '
          f'{s["tv_won_p20"]:>8.1f} {s["tv_won_p50"]:>8.1f} {s["tv_won_p80"]:>8.1f}')

print()
print('=' * 120)
print('[가설 C] 조건 충족 비율 분포 (어느 조건이 70+ 을 만드는가)')
print('=' * 120)
print(f'{"그룹":<10} {"N":>6} {"정배열":>7} {"장대양봉":>8} {"60신고가":>9} {"눌림목":>7} | {"TV3배↑":>7} {"종가95↑":>8} | {"TV비율p50":>10}')
print('-' * 120)
for name, g in groups:
    s = stats(g)
    if not s: continue
    print(f'{name:<10} {s["N"]:>6,} {s["pct_align"]:>6.1f}% {s["pct_big"]:>7.1f}% '
          f'{s["pct_new_high"]:>8.1f}% {s["pct_pullback"]:>6.1f}% | '
          f'{s["tv_ratio_3x"]:>6.1f}% {s["pos_95"]:>7.1f}% | '
          f'{s["tv_ratio_p50"]:>9.2f}x')

# -----------------------------------------------------------------------------
# [가설 E] 70점+ 의 연도별 realized
# -----------------------------------------------------------------------------
print()
print('=' * 120)
print('[가설 E] 점수 구간별 연도 분포')
print('=' * 120)
years = [str(y) for y in range(2014, 2027)]
print(f'{"그룹":<10}', end='')
for y in years:
    print(f' {y[-2:]:>5}', end='')
print()
print('-' * 120)

for name, g in groups:
    if not g: continue
    by_year = defaultdict(list)
    for r in g:
        y = r['date'][:4]
        by_year[y].append(r['gap'])
    line = f'{name:<10}'
    for y in years:
        gaps_y = by_year.get(y, [])
        if len(gaps_y) < 5:
            line += f' {"N/A":>5}'
        else:
            real_y = np.mean(gaps_y) - ROUND_TRIP_COST_PCT
            line += f' {real_y:>+4.1f}'
    print(line)

print()
print('=' * 120)
print('[가설 B] 70점+ 에서 T일 상한가 근접 (+15%+) 진입 상세')
print('=' * 120)
# 70점+ 만 추출
high_score = g_70_75 + g_75_80 + g_80
if high_score:
    day_chs = np.array([r['day_change'] for r in high_score])
    gaps = np.array([r['gap'] for r in high_score])
    # T일 등락률 3구간으로 나누어 각각 gap 평균
    bins = [(None, 5), (5, 10), (10, 15), (15, 20), (20, None)]
    print(f'{"T일 상승률":<15} {"N":>6} {"비율":>6} {"평균gap":>9} {"realized":>10}')
    print('-' * 60)
    for lo_p, hi_p in bins:
        if lo_p is None:
            mask = day_chs < hi_p
            label = f'< {hi_p}%'
        elif hi_p is None:
            mask = day_chs >= lo_p
            label = f'≥ {lo_p}%'
        else:
            mask = (day_chs >= lo_p) & (day_chs < hi_p)
            label = f'[{lo_p}, {hi_p})%'
        n = mask.sum()
        if n == 0: continue
        pct = n / len(day_chs) * 100
        mgap = gaps[mask].mean()
        real = mgap - ROUND_TRIP_COST_PCT
        print(f'{label:<15} {n:>6,} {pct:>5.1f}% {mgap:>+8.2f}% {real:>+9.2f}%')

print()
print('완료.')
