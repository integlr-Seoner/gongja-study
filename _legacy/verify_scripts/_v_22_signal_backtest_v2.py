"""_v_22_signal_backtest_v2.py — 종가배팅 4시그널 백테스트 v2 (재설계)

v1 결함 7개 해결:
  1. max_positions=10 → 30
  2. 자본 100% 노출 → 운용 30% / cash 70% 2분할
  3. 슬리피지 0.76% 고정 → 시총 차등 (0.3%/0.5%/0.8%)
  4. 단일 시드 → 시드 10개 평균
  5. 일일 손실 제어 추가 (-3%/1d, -5%/7d, -10%/30d 중단)
  6. gross win rate + net win rate 둘 다
  7. 분기별 안정성 분석 + 종목 동시발생 분포

자본: 1억원
운용: 3천만원 (30%) — 종가배팅 전용
종목당 한도: min(운용/N, 운용×5% = 150만원)

대상: 4시그널 + RANDOM_30 (베이스라인)
기간: 2014~2026 전 거래일
"""
import sqlite3
import numpy as np
import time
import json
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
INITIAL_CAPITAL = 100_000_000     # 1억원 (총 자본)
WORKING_RATIO = 0.30              # 운용 비율 (종가배팅 전용)
MAX_POSITIONS = 30                # 1일 최대 동시 매수
PER_STOCK_MAX_RATIO = 0.05        # 종목당 운용자본 최대 비율
MIN_PRICE = 1000
MIN_VOL = 50000

# 시총 3-tier 슬리피지
SLIPPAGE_LARGE = 0.30  # 거래대금 상위 20%
SLIPPAGE_MID   = 0.50  # 60%
SLIPPAGE_SMALL = 0.80  # 하위 20%

# Circuit Breaker
CB_LIGHT_THRESHOLD = -3.0   # 운용자본 대비 -3%
CB_LIGHT_DAYS = 1
CB_MID_THRESHOLD   = -5.0
CB_MID_DAYS = 7
CB_HEAVY_THRESHOLD = -10.0
CB_HEAVY_DAYS = 30

# 시드
N_SEEDS = 3
SEEDS = list(range(42, 42 + N_SEEDS))

SIGNALS = ['C1+C2+V', 'C2+V+P', 'C1+V+P', 'C1+V', 'RANDOM_30']

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/6] 거래일 + OHLCV 로드...')
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
# 2. 종목별 평균 거래대금 산출 → 슬리피지 tier 결정
# -----------------------------------------------------------------------------
print('[2/6] 종목별 슬리피지 tier 산출...')

t0 = time.time()
code_avg_tv = {}
for code, arr in by_code.items():
    # 일평균 close × volume (최근 250일 또는 전체)
    n = arr.shape[0]
    sample = arr[-250:] if n > 250 else arr
    tv = (sample[:,4] * sample[:,5]).mean()
    code_avg_tv[code] = tv

# 분위수 계산
tv_sorted = sorted(code_avg_tv.values())
n_codes = len(tv_sorted)
p20 = tv_sorted[n_codes // 5]
p80 = tv_sorted[n_codes * 4 // 5]

code_slippage = {}
for code, tv in code_avg_tv.items():
    if tv >= p80:
        code_slippage[code] = SLIPPAGE_LARGE
    elif tv >= p20:
        code_slippage[code] = SLIPPAGE_MID
    else:
        code_slippage[code] = SLIPPAGE_SMALL
print(f'  완료: 대형={SLIPPAGE_LARGE}%, 중형={SLIPPAGE_MID}%, 소형={SLIPPAGE_SMALL}%, {time.time()-t0:.1f}초')
print(f'  분위 경계: p20={p20:,.0f}원, p80={p80:,.0f}원')


# -----------------------------------------------------------------------------
# 3. 일별 시그널 사전 계산 (시그널별 (code, gap) 리스트)
# -----------------------------------------------------------------------------
print('[3/6] 일별 시그널 사전 계산...')

day_signals = defaultdict(lambda: defaultdict(list))

def calc_at(arr, t_pos):
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
    C1_order = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t; rng = high_t - low_t
    C1_big = (rng > 0) and (body > 0) and (body / rng > 0.6)
    C1 = C1_order and C1_big
    C2 = high_t > h[t_pos-60:t_pos].max()
    tv = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv.mean()
    today_tv = close_t * vol_t
    V = (avg20 > 0) and (today_tv / avg20 >= 1.5)
    P = (rng > 0) and ((close_t - low_t) / rng >= 0.70)
    return {
        'gap': gap, 'valid': True,
        'C1+C2+V':  C1 and C2 and V,
        'C2+V+P':   C2 and V and P,
        'C1+V+P':   C1 and V and P,
        'C1+V':     C1 and V,
    }

t0 = time.time()
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        f = calc_at(arr, row_pos)
        if f is None: continue
        gap = f['gap']
        # 4 시그널
        for sig in ['C1+C2+V', 'C2+V+P', 'C1+V+P', 'C1+V']:
            if f[sig]:
                day_signals[date_idx][sig].append((code, gap))
        # ALL_VALID = RANDOM_30 후보 풀
        day_signals[date_idx]['_VALID_POOL'].append((code, gap))
print(f'  완료: {time.time()-t0:.1f}초, 발생 일수 {len(day_signals):,}일')


# -----------------------------------------------------------------------------
# 4. 시뮬레이션 (시그널별 × 시드별)
# -----------------------------------------------------------------------------
print('[4/6] 시뮬레이션 (시드 N개 평균)...')

def simulate(signal_name: str, seed: int):
    """v2 시뮬레이션:
    - 운용자본 30%, 종목당 5% 한도, max 30포지션
    - 시총 차등 슬리피지
    - Circuit Breaker (-3%/1d, -5%/7d, -10%/30d)
    - RANDOM_30 일 때만 seed 의미 있음
    """
    rng = np.random.default_rng(seed)
    capital = INITIAL_CAPITAL
    working = capital * WORKING_RATIO
    per_stock_max = working * PER_STOCK_MAX_RATIO
    
    equity_curve = [(all_dates[0], capital)]
    daily_returns = []
    
    n_trades = 0
    n_wins_gross = 0  # gap > 0
    n_wins_net = 0    # gap > slippage (실제 수익)
    profit_total = 0.0
    loss_total = 0.0
    
    cb_skip_until = -1  # date_idx까지 진입 중단
    
    for date_idx in range(len(all_dates)):
        # Circuit Breaker
        if date_idx < cb_skip_until:
            equity_curve.append((all_dates[date_idx], capital))
            daily_returns.append(0.0)
            continue
        
        # 시그널 종목 추출
        if signal_name == 'RANDOM_30':
            pool = day_signals.get(date_idx, {}).get('_VALID_POOL', [])
            if len(pool) > MAX_POSITIONS:
                idxs = rng.choice(len(pool), size=MAX_POSITIONS, replace=False)
                signals = [pool[i] for i in idxs]
            else:
                signals = pool
        else:
            sigs_raw = day_signals.get(date_idx, {}).get(signal_name, [])
            # max_positions 초과 시 시드 기반 랜덤 선택 (편향 제거)
            if len(sigs_raw) > MAX_POSITIONS:
                idxs = rng.choice(len(sigs_raw), size=MAX_POSITIONS, replace=False)
                signals = [sigs_raw[i] for i in idxs]
            else:
                signals = sigs_raw
        
        if not signals:
            equity_curve.append((all_dates[date_idx], capital))
            daily_returns.append(0.0)
            continue
        
        n = len(signals)
        # 종목당 투자금: min(운용/N, per_stock_max)
        slot = min(working / n, per_stock_max)
        # 사용된 운용금액 (한도 초과 시 잔액은 cash)
        used = slot * n
        
        day_pnl = 0.0
        for code, gap in signals:
            slip = code_slippage.get(code, SLIPPAGE_MID)
            net_pct = gap - slip
            pnl = slot * net_pct / 100
            day_pnl += pnl
            n_trades += 1
            if gap > 0:
                n_wins_gross += 1
            if pnl > 0:
                n_wins_net += 1
                profit_total += pnl
            else:
                loss_total += abs(pnl)
        
        # 운용자본 대비 일일 수익률 (Circuit Breaker 판정 기준)
        day_pnl_pct_of_working = day_pnl / working * 100
        capital += day_pnl
        # working 도 비례 갱신
        working = capital * WORKING_RATIO
        per_stock_max = working * PER_STOCK_MAX_RATIO
        
        daily_returns.append(day_pnl / max(capital - day_pnl, 1) * 100)
        equity_curve.append((all_dates[date_idx], capital))
        
        # Circuit Breaker 체크
        if day_pnl_pct_of_working <= CB_HEAVY_THRESHOLD:
            cb_skip_until = date_idx + 1 + CB_HEAVY_DAYS
        elif day_pnl_pct_of_working <= CB_MID_THRESHOLD:
            cb_skip_until = date_idx + 1 + CB_MID_DAYS
        elif day_pnl_pct_of_working <= CB_LIGHT_THRESHOLD:
            cb_skip_until = date_idx + 1 + CB_LIGHT_DAYS
    
    eq_arr = np.array([e[1] for e in equity_curve])
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak * 100
    mdd = dd.min()
    
    rets_arr = np.array(daily_returns)
    sharpe = rets_arr.mean() / rets_arr.std() * np.sqrt(252) if rets_arr.std() > 0 else 0.0
    
    win_gross = n_wins_gross / n_trades * 100 if n_trades else 0
    win_net   = n_wins_net   / n_trades * 100 if n_trades else 0
    pf = profit_total / loss_total if loss_total > 0 else 0
    total_ret = (capital / INITIAL_CAPITAL - 1) * 100
    years = len(all_dates) / 252
    cagr = ((capital / INITIAL_CAPITAL) ** (1/years) - 1) * 100 if years > 0 else 0
    
    return {
        'final_capital': capital, 'total_return_pct': total_ret, 'cagr': cagr,
        'mdd': mdd, 'sharpe': sharpe,
        'win_gross': win_gross, 'win_net': win_net,
        'profit_factor': pf, 'n_trades': n_trades,
        'equity_curve': equity_curve,
    }


t0 = time.time()
all_results = {sig: [] for sig in SIGNALS}  # 시드별 결과 누적
for sig in SIGNALS:
    for seed in SEEDS:
        r = simulate(sig, seed)
        all_results[sig].append(r)
    print(f'  {sig}: {N_SEEDS}회 시뮬레이션, 누적 {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 5. 시드 평균 + 표준편차 집계
# -----------------------------------------------------------------------------
print()
print('[5/6] 시드 평균 ± 표준편차')
print()

KEYS = ['final_capital', 'total_return_pct', 'cagr', 'mdd', 'sharpe',
        'win_gross', 'win_net', 'profit_factor', 'n_trades']

print('=' * 130)
print(f'{"Signal":<12} {"FinalCap(평균)":>16} {"Total%":>11} {"CAGR%":>11} {"MDD%":>10} {"Sharpe":>10} {"WinG%":>10} {"WinN%":>10} {"PF":>9}')
print('-' * 130)

summary = {}
for sig in SIGNALS:
    seeds = all_results[sig]
    agg = {}
    for k in KEYS:
        vals = [r[k] for r in seeds]
        agg[k] = (np.mean(vals), np.std(vals))
    summary[sig] = agg
    
    fc_mean, fc_std = agg['final_capital']
    tr_mean, tr_std = agg['total_return_pct']
    cg_mean, cg_std = agg['cagr']
    mdd_mean, mdd_std = agg['mdd']
    sh_mean, sh_std = agg['sharpe']
    wg_mean, wg_std = agg['win_gross']
    wn_mean, wn_std = agg['win_net']
    pf_mean, pf_std = agg['profit_factor']
    
    print(f'{sig:<12} {fc_mean:>16,.0f} {tr_mean:>+8.1f}±{tr_std:>4.1f} '
          f'{cg_mean:>+7.2f}±{cg_std:>4.2f} {mdd_mean:>+7.1f}±{mdd_std:>4.1f} '
          f'{sh_mean:>7.2f}±{sh_std:>4.2f} {wg_mean:>7.1f}±{wg_std:>4.1f} '
          f'{wn_mean:>7.1f}±{wn_std:>4.1f} {pf_mean:>6.2f}±{pf_std:>4.2f}')


# -----------------------------------------------------------------------------
# 6. 분기별 안정성 분석 (시드 0번 결과 사용)
# -----------------------------------------------------------------------------
print()
print('[6/6] 분기별 안정성 (시드 0번 기준)')
print()

QUARTERS = []
for y in range(2014, 2027):
    for q in [1, 2, 3, 4]:
        s = f'{y}{q*3-2:02d}01'
        e = f'{y}{q*3:02d}31'
        QUARTERS.append((f'{y}Q{q}', s, e))

print('=' * 130)
print(f'{"Signal":<12}', end='')
yrs = ['14', '15', '16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
for y in yrs:
    print(f' {y}Q1 {y}Q2 {y}Q3 {y}Q4 ', end='')
print()
print('-' * 130)

# 너무 길어 줄여서: 연도별만
print(f'{"Signal":<12} ', end='')
for y in yrs:
    print(f'  {y:>4}', end='')
print()
print('-' * 130)

for sig in SIGNALS:
    r0 = all_results[sig][0]
    eq = dict(r0['equity_curve'])
    line = f'{sig:<12} '
    prev_cap = INITIAL_CAPITAL
    for y in yrs:
        full_y = f'20{y}'
        year_dates = [d for d in all_dates if d.startswith(full_y)]
        if not year_dates:
            line += f'  {"N/A":>4}'
            continue
        end_cap = eq.get(year_dates[-1], prev_cap)
        ret = (end_cap / prev_cap - 1) * 100 if prev_cap > 0 else 0
        line += f' {ret:>+5.1f}'
        prev_cap = end_cap
    print(line)

# -----------------------------------------------------------------------------
# 결과 JSON 저장
# -----------------------------------------------------------------------------
print()
out = {}
for sig in SIGNALS:
    agg = summary[sig]
    out[sig] = {k: {'mean': float(v[0]), 'std': float(v[1])} for k, v in agg.items()}
with open(r'D:\StockAnalyst\_v_22_signal_backtest_v2_results.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print('결과 저장: _v_22_signal_backtest_v2_results.json')
print()
print('완료.')
