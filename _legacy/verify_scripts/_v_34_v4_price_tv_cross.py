"""_v_34_v4_price_tv_cross.py — 가격대 × 거래대금 교차 분석

_v_33 결과:
  - 가격대: 저가(~2k) realized +4.887% (최강)
  - 거래대금: 대형(200~1000억) realized +3.600% (최강)

가설: "저가 + 대형 거래대금" 조합이 최강? 아니면 별개?

측정:
  score==4 종목을 가격×거래대금 매트릭스로 분해하여 교차 효과 확인.
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
    return {'gap': gap, 'score': score, 'close': close_t, 'tv_won': today_tv}


print('[2/3] V4 점수 수집 (score==4 만)...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = v4_at(arr, row_pos)
        if r is None or r['score'] != 4: continue
        records.append(r)
print(f'  수집: {len(records)}건, {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 가격대 × 거래대금 매트릭스
# -----------------------------------------------------------------------------
PRICE_BINS = [
    (0, 2000, '저가'),
    (2000, 5000, '저-중'),
    (5000, 10000, '중가'),
    (10000, 30000, '중-고'),
    (30000, 999999999, '고가'),
]
TV_BINS = [
    (0, 50, '소형'),
    (50, 200, '중형'),
    (200, 1000, '대형'),
    (1000, 999999999, '초대형'),
]


print()
print('=' * 110)
print('[3/3] 가격대 × 거래대금 매트릭스 (score==4)')
print('=' * 110)

# 헤더
header_label = '가격|거래대금'
print(f'{header_label:<12}', end='')
for lo_t, hi_t, tv_name in TV_BINS:
    print(f' {tv_name:>20}', end='')
print(f' {"전체":>14}')
print('-' * 110)

# 각 셀: N | mean
results = {}
for lo_p, hi_p, p_name in PRICE_BINS:
    print(f'{p_name:<12}', end='')
    row_all = []
    for lo_t, hi_t, tv_name in TV_BINS:
        sub = [r for r in records
               if lo_p <= r['close'] < hi_p
               and lo_t <= r['tv_won']/1e8 < hi_t]
        if len(sub) < 3:
            print(f' {"(N<3)":>20}', end='')
        else:
            gaps = np.array([r['gap'] for r in sub])
            mean = gaps.mean()
            win = (gaps > 0).mean() * 100
            print(f' {len(sub):>4} {mean:>+6.2f}% w{win:>4.0f}%', end='')
            results[(p_name, tv_name)] = {
                'n': len(sub), 'mean': mean, 'win': win,
                'real': mean - ROUND_TRIP_COST_PCT
            }
            row_all += list(gaps)
    # 가격대 전체
    if row_all:
        arr = np.array(row_all)
        print(f' {len(arr):>4} {arr.mean():>+6.2f}%', end='')
    print()

# 거래대금 전체
print(f'{"전체":<12}', end='')
for lo_t, hi_t, tv_name in TV_BINS:
    sub = [r for r in records if lo_t <= r['tv_won']/1e8 < hi_t]
    if len(sub) < 3:
        print(f' {"(N<3)":>20}', end='')
    else:
        gaps = np.array([r['gap'] for r in sub])
        print(f' {len(sub):>4} {gaps.mean():>+6.2f}% w{(gaps>0).mean()*100:>4.0f}%', end='')
print(f' {len(records):>4} {np.mean([r["gap"] for r in records]):>+6.2f}%')

# -----------------------------------------------------------------------------
# 최강 셀 식별
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('최강 셀 (realized 내림차순, N >= 10)')
print('=' * 110)
sorted_cells = sorted(
    [(k, v) for k, v in results.items() if v['n'] >= 10],
    key=lambda x: -x[1]['real']
)
print(f'{"셀":<20} {"N":>6} {"mean":>9} {"승률":>8} {"realized":>10}')
print('-' * 110)
for (p, t), v in sorted_cells[:10]:
    tag = ' ⭐' if v['real'] > 4 else ''
    print(f'{p:<6}+{t:<12} {v["n"]:>6} {v["mean"]:>+8.2f}% '
          f'{v["win"]:>7.1f}% {v["real"]:>+9.3f}%{tag}')

print()
print('약한 셀 (realized 오름차순, N >= 10)')
print('-' * 110)
for (p, t), v in sorted_cells[-5:]:
    print(f'{p:<6}+{t:<12} {v["n"]:>6} {v["mean"]:>+8.2f}% '
          f'{v["win"]:>7.1f}% {v["real"]:>+9.3f}%')

print()
print('완료.')
