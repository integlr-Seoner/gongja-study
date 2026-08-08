"""_v_20_closing_bet_period_check.py — 시기 분할 검증 (Period Stability)

목적: _v_19 의 결과가 특정 시기에만 유효한 게 아닌지 확인.
구간 분할: P1=2014~2018 / P2=2019~2022 / P3=2023~2026

방법론: _v_19 의 알고리즘과 동일하나 (date, gap) 튜플로 저장하고
구간별 + 그룹별 mean/realized 계산.

판정 기준:
  ① 모든 구간에서 realized > 0 이면 안정
  ② 한 구간이라도 음수면 시기 의존성 의심
  ③ 구간 간 mean 표준편차가 mean 절댓값의 50% 초과 시 불안정
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

PERIODS = {
    'P1_2014_2018': ('20140101', '20181231'),
    'P2_2019_2022': ('20190101', '20221231'),
    'P3_2023_2026': ('20230101', '20261231'),
}

def period_of(date_str):
    for name, (s, e) in PERIODS.items():
        if s <= date_str <= e:
            return name
    return None

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/4] 샘플 날짜 추출...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
samples = []
current_ym = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != current_ym and dd >= 15:
        samples.append(d); current_ym = ym
sample_idx_to_date = {date_index[d]: d for d in samples if d in date_index}
sample_idx_set = set(sample_idx_to_date)
print(f'  샘플: {len(samples)}개')

print('[2/4] 보통주 OHLCV 메모리 로드...')
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

GROUPS = {
    'C1':       lambda f: f['C1'],
    'C2':       lambda f: f['C2'],
    'V':        lambda f: f['V'],
    'P':        lambda f: f['P'],
    'C1+V':     lambda f: f['C1'] and f['V'],
    'C2+V':     lambda f: f['C2'] and f['V'],
    'C2+V+P':   lambda f: f['C2'] and f['V'] and f['P'],
    'C1+V+P':   lambda f: f['C1'] and f['V'] and f['P'],
    'C1+C2+V':  lambda f: f['C1'] and f['C2'] and f['V'],
}
# results[group][period] = [gap, gap, ...]
results = {g: {p: [] for p in PERIODS} for g in GROUPS}

def calc_at(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o,h,lo,c,v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    C1_order = ma5 > ma10 > ma20
    body = close_t - open_t; rng = high_t - low_t
    C1_big = (rng > 0) and (body > 0) and (body / rng > 0.6)
    C1 = C1_order and C1_big
    C2 = high_t > h[t_pos-60:t_pos].max()
    tv = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv.mean()
    today_tv = close_t * vol_t
    V = (avg20 > 0) and (today_tv / avg20 >= 1.5)
    P = (rng > 0) and ((close_t - low_t) / rng >= 0.70)
    return {'gap': gap, 'C1': C1, 'C2': C2, 'V': V, 'P': P}

print('[3/4] 샘플 순회...')
t0 = time.time()
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        f = calc_at(arr, row_pos)
        if f is None: continue
        date_str = sample_idx_to_date[date_idx]
        period = period_of(date_str)
        if not period: continue
        gap = f['gap']
        for name, fn in GROUPS.items():
            if fn(f):
                results[name][period].append(gap)
print(f'  계산: {time.time()-t0:.1f}초')
print()

print('[4/4] 시기별 통계 출력...')
print()
print('=' * 100)
print(f'{"Group":<10}', end='')
for p in PERIODS:
    print(f'  {p:<14}', end='')
print(f'  {"전체평균":<10}  {"안정성":<10}')
print(f'{"":<10}', end='')
for p in PERIODS:
    print(f'  {"N | real%":<14}', end='')
print()
print('-' * 100)

for group, period_data in results.items():
    means = []
    line = f'{group:<10}'
    for p in PERIODS:
        arr = period_data[p]
        if not arr:
            line += f'  {"N=0":<14}'
            means.append(None)
        else:
            a = np.array(arr)
            mean = a.mean()
            real = mean - ROUND_TRIP_COST_PCT
            means.append(real)
            line += f'  {len(arr):>4d}|{real:>+7.3f}'
    valid_means = [m for m in means if m is not None]
    if len(valid_means) == 3:
        avg = np.mean(valid_means)
        std = np.std(valid_means)
        # 안정성 판정: 모든 구간 양수 + 표준편차/절댓값평균 < 0.5
        all_positive = all(m > 0 for m in valid_means)
        stability = 'STABLE' if all_positive else 'UNSTABLE'
        if all_positive and abs(avg) > 0:
            cv = std / abs(avg)
            if cv > 0.5:
                stability = 'VOLATILE'
        line += f'  {avg:>+7.3f}    {stability:<10}'
    print(line)

print()
print('=' * 100)
print('판정 기준:')
print('  STABLE   = 3개 구간 모두 realized > 0 AND 변동계수 < 0.5')
print('  VOLATILE = 3개 구간 모두 양수이나 변동계수 ≥ 0.5')
print('  UNSTABLE = 한 구간이라도 realized ≤ 0')
print()

# 가장 안정적인 그룹 추출
print('=' * 100)
print('운영 채택 후보 (STABLE 그룹만):')
print('=' * 100)
stable_groups = []
for group, period_data in results.items():
    means = []
    for p in PERIODS:
        arr = period_data[p]
        if arr:
            a = np.array(arr)
            means.append(a.mean() - ROUND_TRIP_COST_PCT)
        else:
            means.append(None)
    valid = [m for m in means if m is not None]
    if len(valid) == 3 and all(m > 0 for m in valid):
        avg = np.mean(valid)
        std = np.std(valid)
        cv = std / abs(avg) if abs(avg) > 0 else 999
        if cv < 0.5:
            n_total = sum(len(period_data[p]) for p in PERIODS)
            stable_groups.append({'group': group, 'avg_realized': avg,
                                  'std': std, 'cv': cv, 'N': n_total,
                                  'periods': dict(zip(PERIODS, valid))})

if stable_groups:
    for g in sorted(stable_groups, key=lambda x: -x['avg_realized']):
        print(f"  {g['group']:<10}  avg_realized={g['avg_realized']:+.3f}%  "
              f"cv={g['cv']:.2f}  N={g['N']:,}")
        for p, m in g['periods'].items():
            print(f"      {p}: realized={m:+.3f}%")
else:
    print('  없음 — 모든 그룹이 시기 의존성 또는 변동성 보임')

conn.close()
print()
print('완료.')
