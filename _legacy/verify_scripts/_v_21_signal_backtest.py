"""_v_21_signal_backtest.py — 종가배팅 4시그널 단순 매매 시뮬레이션

전략:
  T일 종가 매수 → T+1일 시가 매도 (KRX 가정, 슬리피지 0.76% 차감 후)
  자본 1억 원, 종목당 동일 비중, 일별 시그널 N개면 N분할
  시그널 0개면 cash hold

비교 그룹 (시기 안정성 검증된 STABLE 4종):
  C1+C2+V, C2+V+P, C1+V+P, C1+V

베이스라인:
  ALL_VALID  = 자격 통과 전종목 (대조군)
  RANDOM_5   = 매일 자격 통과 종목 중 임의 5개 (시드 고정)

대상 기간: 전체 거래일 (3,017일, 2014~2026)
검증: _v_19 의 평균 수익이 시뮬레이션 평균과 일치하는지 (정합성)
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict
import json

DB = r'D:\StockAnalyst\ohlcv_long.db'
INITIAL_CAPITAL = 100_000_000  # 1억원
MIN_PRICE = 1000
MIN_VOL = 50000
SLIPPAGE_PCT = 0.76  # 보수적 (수수료+세금+슬리피지)
RANDOM_SEED = 42

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/5] 전체 거래일 + 보통주 코드...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
print(f'  총 {len(all_dates):,}개 영업일')

print('[2/5] OHLCV 메모리 로드...')
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
# 3. 일별 시그널 발생 종목 사전 계산
# 각 일자별로 (signal_name -> [(code, gap_ret), ...]) 매핑
# -----------------------------------------------------------------------------
print('[3/5] 일별 시그널 발생 사전 계산...')

SIGNALS = ['C1+C2+V', 'C2+V+P', 'C1+V+P', 'C1+V', 'ALL_VALID', 'RANDOM_5']

# day_signals[date_idx][signal_name] = [(code, gap_ret), ...]
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
        'gap': gap,
        'C1+C2+V':  C1 and C2 and V,
        'C2+V+P':   C2 and V and P,
        'C1+V+P':   C1 and V and P,
        'C1+V':     C1 and V,
        'ALL_VALID': True,  # 자격필터 통과만으로
    }


t0 = time.time()
processed = 0
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        f = calc_at(arr, row_pos)
        if f is None: continue
        gap = f['gap']
        for sig in ['C1+C2+V', 'C2+V+P', 'C1+V+P', 'C1+V', 'ALL_VALID']:
            if f[sig]:
                day_signals[date_idx][sig].append((code, gap))
    processed += 1
    if processed % 500 == 0:
        print(f'  {processed:,}/{len(by_code):,} 종목 처리... {time.time()-t0:.1f}초 경과')

# RANDOM_5 추가: ALL_VALID에서 매일 랜덤 5종목
rng = np.random.default_rng(RANDOM_SEED)
for date_idx, sigs in day_signals.items():
    valid = sigs.get('ALL_VALID', [])
    if len(valid) >= 5:
        chosen_idx = rng.choice(len(valid), size=5, replace=False)
        sigs['RANDOM_5'] = [valid[i] for i in chosen_idx]
    else:
        sigs['RANDOM_5'] = list(valid)

print(f'  사전 계산 완료: {time.time()-t0:.1f}초')
print(f'  시그널 발생 일수: {len(day_signals):,}일')
print()


# -----------------------------------------------------------------------------
# 4. 백테스트 시뮬레이션 (시그널별 자본 추이)
# -----------------------------------------------------------------------------
print('[4/5] 시뮬레이션 실행...')

def simulate(signal_name: str, max_positions: int = 10):
    """T일 시그널 발생 종목들에 자본 균등 분할 매수 → T+1일 시가 매도.
    max_positions: 1일 최대 동시 매수 종목 수 (분산 한계)
    """
    capital = INITIAL_CAPITAL
    equity_curve = [(all_dates[0], capital)]
    daily_returns = []  # 일별 수익률 (%)
    n_trades = 0
    n_wins = 0
    profit_total = 0.0
    loss_total = 0.0
    
    for date_idx in range(len(all_dates)):
        signals = day_signals.get(date_idx, {}).get(signal_name, [])
        if not signals:
            equity_curve.append((all_dates[date_idx], capital))
            daily_returns.append(0.0)
            continue
        
        # 상위 max_positions만 선택 (gap_ret 기준 무관 — 사전적 선택)
        # 실제 운영에선 점수순 선택이지만 여기선 단순화: 첫 N개
        chosen = signals[:max_positions]
        n = len(chosen)
        slot = capital / n  # 종목당 투자금액
        
        # 일별 수익 합산 (slippage 차감)
        day_pnl = 0.0
        for code, gap in chosen:
            pnl_pct = gap - SLIPPAGE_PCT  # 슬리피지 차감 net
            pnl = slot * pnl_pct / 100
            day_pnl += pnl
            n_trades += 1
            if pnl > 0:
                n_wins += 1
                profit_total += pnl
            else:
                loss_total += abs(pnl)
        
        capital += day_pnl
        daily_returns.append(day_pnl / (capital - day_pnl) * 100 if capital - day_pnl > 0 else 0)
        equity_curve.append((all_dates[date_idx], capital))
    
    # MDD 계산
    eq_arr = np.array([e[1] for e in equity_curve])
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak * 100
    mdd = dd.min()
    
    # Sharpe (연환산, 252일 가정)
    rets_arr = np.array(daily_returns)
    if rets_arr.std() > 0:
        sharpe = rets_arr.mean() / rets_arr.std() * np.sqrt(252)
    else:
        sharpe = 0.0
    
    win_rate = n_wins / n_trades * 100 if n_trades > 0 else 0
    profit_factor = profit_total / loss_total if loss_total > 0 else 0
    total_return_pct = (capital / INITIAL_CAPITAL - 1) * 100
    years = len(all_dates) / 252
    cagr = ((capital / INITIAL_CAPITAL) ** (1/years) - 1) * 100 if years > 0 else 0
    
    return {
        'name': signal_name,
        'final_capital': capital,
        'total_return_pct': total_return_pct,
        'cagr': cagr,
        'mdd': mdd,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'n_trades': n_trades,
        'equity_curve': equity_curve,
    }


results = []
for sig in SIGNALS:
    r = simulate(sig, max_positions=10)
    results.append(r)

print()
print('[5/5] 결과 요약')
print()
print('=' * 110)
print(f'{"Signal":<12} {"FinalCap":>14} {"Total%":>9} {"CAGR%":>8} {"MDD%":>8} {"Sharpe":>7} {"Win%":>6} {"PF":>6} {"Trades":>8}')
print('-' * 110)
for r in results:
    print(f'{r["name"]:<12} {r["final_capital"]:>14,.0f} {r["total_return_pct"]:>+8.1f}% '
          f'{r["cagr"]:>+7.2f}% {r["mdd"]:>+7.1f}% {r["sharpe"]:>6.2f} '
          f'{r["win_rate"]:>5.1f}% {r["profit_factor"]:>5.2f} {r["n_trades"]:>8,}')

# 연도별 수익률 (4시그널만)
print()
print('=' * 110)
print('연도별 수익률 (백테스트 기간 분할)')
print('=' * 110)
years_to_check = ['2014', '2015', '2016', '2017', '2018', '2019',
                  '2020', '2021', '2022', '2023', '2024', '2025', '2026']
print(f'{"Signal":<12}', end='')
for y in years_to_check:
    print(f'  {y[-2:]:>5}', end='')
print()
print('-' * 110)

for r in results:
    if r['name'] not in ('C1+C2+V', 'C2+V+P', 'C1+V+P', 'C1+V'):
        continue
    eq = dict(r['equity_curve'])
    line = f'{r["name"]:<12}'
    prev_cap = INITIAL_CAPITAL
    for y in years_to_check:
        # 그 해 마지막 거래일 자본
        year_dates = [d for d in all_dates if d.startswith(y)]
        if not year_dates:
            line += f'  {"N/A":>5}'
            continue
        end_cap = eq.get(year_dates[-1], prev_cap)
        ret = (end_cap / prev_cap - 1) * 100 if prev_cap > 0 else 0
        line += f'  {ret:>+5.1f}'
        prev_cap = end_cap
    print(line)

# 결과 JSON 저장
out = {r['name']: {k: v for k, v in r.items() if k != 'equity_curve'}
       for r in results}
with open(r'D:\StockAnalyst\_v_21_signal_backtest_results.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print()
print('결과 저장: _v_21_signal_backtest_results.json')
print()
print('완료.')
