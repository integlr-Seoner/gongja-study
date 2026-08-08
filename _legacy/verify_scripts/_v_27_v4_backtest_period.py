"""_v_27_v4_backtest_period.py — V4 백테스트 + 시기 분할 검증

V4 정의: 정배열+장대양봉 / 60일 신고가 / 거래대금 3배↑ / 종가 95%↑
점수 0~4 (각 조건 1점)

운영 모드:
  Mode A: score==4 만 매수 (STRONG_BUY only)
  Mode B: score==4 우선 + 부족시 score==3 보충 (max 30)

설정 (_v_22 동일):
  자본 1억, 운용 30%, 종목당 5%, max 30포지션
  슬리피지 차등 0.3/0.5/0.8%
  Circuit Breaker -3%/1d, -5%/7d, -10%/30d
  시드 3개 평균
  시기 분할: P1(2014-2018)/P2(2019-2022)/P3(2023-2026)
"""
import sqlite3
import numpy as np
import time
import json
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
INITIAL_CAPITAL = 100_000_000
WORKING_RATIO = 0.30
MAX_POSITIONS = 30
PER_STOCK_MAX_RATIO = 0.05
MIN_PRICE = 1000
MIN_VOL = 50000

SLIPPAGE_LARGE = 0.30
SLIPPAGE_MID   = 0.50
SLIPPAGE_SMALL = 0.80

CB_LIGHT = (-3.0, 1)
CB_MID   = (-5.0, 7)
CB_HEAVY = (-10.0, 30)

N_SEEDS = 3
SEEDS = list(range(42, 42 + N_SEEDS))

PERIODS = {
    'P1_2014_2018': ('20140101', '20181231'),
    'P2_2019_2022': ('20190101', '20221231'),
    'P3_2023_2026': ('20230101', '20261231'),
}

def period_of(d):
    for n, (s, e) in PERIODS.items():
        if s <= d <= e: return n
    return None

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/5] 거래일 + OHLCV 로드...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
print(f'  거래일: {len(all_dates):,}')

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

print('[2/5] 슬리피지 tier 산출...')
code_avg_tv = {}
for code, arr in by_code.items():
    sample = arr[-250:] if arr.shape[0] > 250 else arr
    code_avg_tv[code] = (sample[:,4] * sample[:,5]).mean()
tv_sorted = sorted(code_avg_tv.values())
n_codes = len(tv_sorted)
p20 = tv_sorted[n_codes // 5]
p80 = tv_sorted[n_codes * 4 // 5]
code_slip = {}
for code, tv in code_avg_tv.items():
    if tv >= p80: code_slip[code] = SLIPPAGE_LARGE
    elif tv >= p20: code_slip[code] = SLIPPAGE_MID
    else: code_slip[code] = SLIPPAGE_SMALL
conn.close()
print(f'  완료')


# -----------------------------------------------------------------------------
# 3. V4 점수 + 일별 시그널 사전 계산
# -----------------------------------------------------------------------------
print('[3/5] V4 점수 사전 계산...')

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

# day_sigs[date_idx][score] = [(code, gap), ...]
day_sigs = defaultdict(lambda: defaultdict(list))
t0 = time.time()
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        r = v4_at(arr, row_pos)
        if r is None: continue
        day_sigs[date_idx][r['score']].append((code, r['gap']))
print(f'  완료: {len(day_sigs):,}일, {time.time()-t0:.1f}초')

# 통계 — score 분포
sc_counts = defaultdict(int)
for sigs in day_sigs.values():
    for s, lst in sigs.items():
        sc_counts[s] += len(lst)
print(f'  score 4: {sc_counts[4]:,}건, score 3: {sc_counts[3]:,}건, score 2: {sc_counts[2]:,}건')


# -----------------------------------------------------------------------------
# 4. 시뮬레이션 (Mode A / Mode B)
# -----------------------------------------------------------------------------
print('[4/5] 시뮬레이션...')

def simulate(mode: str, seed: int):
    """mode: 'A' (score==4 만), 'B' (4 우선 + 3 보충)"""
    rng = np.random.default_rng(seed)
    capital = INITIAL_CAPITAL
    working = capital * WORKING_RATIO
    per_max = working * PER_STOCK_MAX_RATIO
    
    equity = [(all_dates[0], capital)]
    daily_rets = []
    period_pnl = {p: [] for p in PERIODS}  # 시기별 일별 수익률 누적
    
    n_trades = 0
    n_wins_g = 0; n_wins_n = 0
    profit = 0.0; loss = 0.0
    cb_skip_until = -1
    
    for date_idx in range(len(all_dates)):
        if date_idx < cb_skip_until:
            equity.append((all_dates[date_idx], capital))
            daily_rets.append(0.0)
            continue
        
        sigs_4 = day_sigs.get(date_idx, {}).get(4, [])
        sigs_3 = day_sigs.get(date_idx, {}).get(3, []) if mode == 'B' else []
        
        # 종목 선정
        if mode == 'A':
            chosen = sigs_4[:MAX_POSITIONS] if len(sigs_4) <= MAX_POSITIONS else \
                     [sigs_4[i] for i in rng.choice(len(sigs_4), MAX_POSITIONS, replace=False)]
        else:  # B
            if len(sigs_4) >= MAX_POSITIONS:
                chosen = [sigs_4[i] for i in rng.choice(len(sigs_4), MAX_POSITIONS, replace=False)]
            else:
                # score=4 모두 + score=3 보충
                need = MAX_POSITIONS - len(sigs_4)
                if len(sigs_3) > need:
                    sup = [sigs_3[i] for i in rng.choice(len(sigs_3), need, replace=False)]
                else:
                    sup = sigs_3
                chosen = sigs_4 + sup
        
        if not chosen:
            equity.append((all_dates[date_idx], capital))
            daily_rets.append(0.0)
            continue
        
        n = len(chosen)
        slot = min(working / n, per_max)
        day_pnl = 0.0
        for code, gap in chosen:
            slip = code_slip.get(code, SLIPPAGE_MID)
            net = gap - slip
            pnl = slot * net / 100
            day_pnl += pnl
            n_trades += 1
            if gap > 0: n_wins_g += 1
            if pnl > 0:
                n_wins_n += 1; profit += pnl
            else:
                loss += abs(pnl)
        
        day_pnl_pct = day_pnl / working * 100
        capital += day_pnl
        working = capital * WORKING_RATIO
        per_max = working * PER_STOCK_MAX_RATIO
        daily_rets.append(day_pnl / max(capital - day_pnl, 1) * 100)
        equity.append((all_dates[date_idx], capital))
        
        # 시기별 PnL
        d_str = all_dates[date_idx]
        p = period_of(d_str)
        if p:
            period_pnl[p].append(day_pnl_pct)
        
        # Circuit Breaker
        if day_pnl_pct <= CB_HEAVY[0]:
            cb_skip_until = date_idx + 1 + CB_HEAVY[1]
        elif day_pnl_pct <= CB_MID[0]:
            cb_skip_until = date_idx + 1 + CB_MID[1]
        elif day_pnl_pct <= CB_LIGHT[0]:
            cb_skip_until = date_idx + 1 + CB_LIGHT[1]
    
    eq_arr = np.array([e[1] for e in equity])
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak * 100
    mdd = dd.min()
    rets = np.array(daily_rets)
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0
    win_g = n_wins_g / n_trades * 100 if n_trades else 0
    win_n = n_wins_n / n_trades * 100 if n_trades else 0
    pf = profit / loss if loss > 0 else 0
    total_ret = (capital / INITIAL_CAPITAL - 1) * 100
    years = len(all_dates) / 252
    cagr = ((capital / INITIAL_CAPITAL) ** (1/years) - 1) * 100 if years > 0 else 0
    
    return {
        'final': capital, 'total': total_ret, 'cagr': cagr,
        'mdd': mdd, 'sharpe': sharpe,
        'win_g': win_g, 'win_n': win_n, 'pf': pf, 'n_trades': n_trades,
        'period_pnl': {p: np.mean(v) if v else 0.0 for p, v in period_pnl.items()},
        'equity': equity,
    }


t0 = time.time()
all_results = {'A': [], 'B': []}
for mode in ['A', 'B']:
    for seed in SEEDS:
        all_results[mode].append(simulate(mode, seed))
    print(f'  Mode {mode}: {N_SEEDS}회, 누적 {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 5. 결과 출력
# -----------------------------------------------------------------------------
print()
print('=' * 130)
print('[5/5] V4 백테스트 결과 (시드 평균 ± 표준편차)')
print('=' * 130)
print(f'{"Mode":<8} {"FinalCap":>16} {"Total%":>13} {"CAGR%":>11} {"MDD%":>10} {"Sharpe":>10} {"WinG%":>10} {"WinN%":>10} {"PF":>9} {"Trades":>8}')
print('-' * 130)

KEYS = ['final', 'total', 'cagr', 'mdd', 'sharpe', 'win_g', 'win_n', 'pf', 'n_trades']
summary = {}
for mode in ['A', 'B']:
    seeds = all_results[mode]
    agg = {k: (np.mean([r[k] for r in seeds]), np.std([r[k] for r in seeds])) for k in KEYS}
    summary[mode] = agg
    print(f'Mode {mode:<3} {agg["final"][0]:>16,.0f} '
          f'{agg["total"][0]:>+9.1f}±{agg["total"][1]:>4.1f} '
          f'{agg["cagr"][0]:>+7.2f}±{agg["cagr"][1]:>4.2f} '
          f'{agg["mdd"][0]:>+7.1f}±{agg["mdd"][1]:>4.1f} '
          f'{agg["sharpe"][0]:>7.2f}±{agg["sharpe"][1]:>4.2f} '
          f'{agg["win_g"][0]:>7.1f}±{agg["win_g"][1]:>4.1f} '
          f'{agg["win_n"][0]:>7.1f}±{agg["win_n"][1]:>4.1f} '
          f'{agg["pf"][0]:>6.2f}±{agg["pf"][1]:>4.2f} '
          f'{agg["n_trades"][0]:>8,.0f}')


# -----------------------------------------------------------------------------
# 6. 시기 분할 (P1/P2/P3) 안정성
# -----------------------------------------------------------------------------
print()
print('=' * 130)
print('시기 분할 안정성 — 일별 운용자본 대비 PnL% 평균 (시드 0번 기준)')
print('=' * 130)
print(f'{"Mode":<8}', end='')
for p in PERIODS: print(f'  {p:<14}', end='')
print(f'  {"avg_real":<10}  {"cv":<6}  {"판정":<10}')
print('-' * 130)

period_judgment = {}
for mode in ['A', 'B']:
    r0 = all_results[mode][0]
    pp = r0['period_pnl']
    vals = [pp[p] for p in PERIODS]
    avg = np.mean(vals)
    std = np.std(vals)
    cv = std / abs(avg) if abs(avg) > 0 else 999
    all_pos = all(v > 0 for v in vals)
    if all_pos and cv < 0.5: judgment = 'STABLE'
    elif all_pos: judgment = 'VOLATILE'
    else: judgment = 'UNSTABLE'
    period_judgment[mode] = {'periods': dict(zip(PERIODS, vals)),
                              'avg': avg, 'cv': cv, 'judgment': judgment}
    line = f'Mode {mode:<3}'
    for v in vals:
        line += f'  {v:>+11.4f}%'
    line += f'  {avg:>+8.4f}%  {cv:>5.2f}  {judgment:<10}'
    print(line)

# -----------------------------------------------------------------------------
# 7. 연도별 수익률 (Mode A, B)
# -----------------------------------------------------------------------------
print()
print('=' * 130)
print('연도별 자본 수익률')
print('=' * 130)
yrs = ['14','15','16','17','18','19','20','21','22','23','24','25','26']
print(f'{"Mode":<8}', end='')
for y in yrs: print(f'  {y:>5}', end='')
print()
print('-' * 130)
for mode in ['A', 'B']:
    r0 = all_results[mode][0]
    eq = dict(r0['equity'])
    line = f'Mode {mode:<3}'
    prev_cap = INITIAL_CAPITAL
    for y in yrs:
        full_y = f'20{y}'
        year_dates = [d for d in all_dates if d.startswith(full_y)]
        if not year_dates:
            line += f'  {"N/A":>5}'; continue
        end_cap = eq.get(year_dates[-1], prev_cap)
        ret = (end_cap / prev_cap - 1) * 100 if prev_cap > 0 else 0
        line += f'  {ret:>+5.1f}'
        prev_cap = end_cap
    print(line)


# -----------------------------------------------------------------------------
# 8. JSON 저장
# -----------------------------------------------------------------------------
out = {}
for mode in ['A', 'B']:
    agg = summary[mode]
    out[mode] = {
        'metrics': {k: {'mean': float(v[0]), 'std': float(v[1])} for k, v in agg.items()},
        'period': {
            p: float(period_judgment[mode]['periods'][p]) for p in PERIODS
        },
        'judgment': period_judgment[mode]['judgment'],
        'period_avg': float(period_judgment[mode]['avg']),
        'period_cv': float(period_judgment[mode]['cv']),
    }
out['_meta'] = {
    'capital': INITIAL_CAPITAL, 'working_ratio': WORKING_RATIO,
    'max_positions': MAX_POSITIONS, 'per_stock_max': PER_STOCK_MAX_RATIO,
    'slippage': {'large': SLIPPAGE_LARGE, 'mid': SLIPPAGE_MID, 'small': SLIPPAGE_SMALL},
    'cb': {'light': CB_LIGHT, 'mid': CB_MID, 'heavy': CB_HEAVY},
    'seeds': SEEDS, 'periods': {k: list(v) for k, v in PERIODS.items()},
    'sc_counts': {str(k): int(v) for k, v in sc_counts.items()},
}
with open(r'D:\StockAnalyst\_v_27_v4_backtest_results.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print()
print('결과 저장: _v_27_v4_backtest_results.json')
print()
print('완료.')
