"""_v_38_market_rotation_kospi_kosdaq.py — KOSPI vs KOSDAQ 로테이션 전략 탐색

배경:
  진짜 섹터 로테이션은 섹터 매핑 한계(11%)로 불가.
  대안: KOSPI/KOSDAQ 지수 로테이션 — 데이터 완비 + 명확한 이분법.

탐색 가설 4개:
  H1 모멘텀 추종: 지난 20일 더 오른 지수에 100% 비중
  H2 평균 회귀:   지난 60일 덜 오른 지수에 100% 비중
  H3 스프레드:    KOSPI 20d - KOSDAQ 20d > +3%p → KOSDAQ 매수
  H4 변동성:      지난 20일 std 낮은 지수 100% 비중

비교군:
  B1 KOSPI 100%
  B2 KOSDAQ 100%
  B3 50:50 분산 (벤치마크)

측정 기간: 2014-01 ~ 2026-04 (13년), 월 1회 리밸런싱
성과 지표: CAGR, MDD, Sharpe, 승률
"""
import sqlite3
import numpy as np
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/4] KOSPI / KOSDAQ 지수 로드...')
kospi = cur.execute(
    "SELECT date, close FROM daily_index_long "
    "WHERE symbol='KOSPI' AND date >= '20140101' ORDER BY date"
).fetchall()
kosdaq = cur.execute(
    "SELECT date, close FROM daily_index_long "
    "WHERE symbol='KOSDAQ' AND date >= '20140101' ORDER BY date"
).fetchall()
conn.close()

kospi_dict = {d: c for d, c in kospi}
kosdaq_dict = {d: c for d, c in kosdaq}
common_dates = sorted(set(kospi_dict.keys()) & set(kosdaq_dict.keys()))
print(f'  공통 거래일: {len(common_dates):,}일 ({common_dates[0]} ~ {common_dates[-1]})')

kospi_c = np.array([kospi_dict[d] for d in common_dates])
kosdaq_c = np.array([kosdaq_dict[d] for d in common_dates])
dates = np.array(common_dates)
n = len(common_dates)


# -----------------------------------------------------------------------------
# 2. 월 1회 리밸런싱 시점 (각 달의 15일 이후 첫 거래일)
# -----------------------------------------------------------------------------
print('\n[2/4] 리밸런싱 시점 결정 (월별)...')
rebal_indices = []
cy = ''
for i, d in enumerate(common_dates):
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        rebal_indices.append(i); cy = ym
# T+20 수익 측정 위해 마지막 리밸런싱 이후 20일 이상 여유 필요
rebal_indices = [i for i in rebal_indices if i + 20 < n]
print(f'  리밸런싱 시점: {len(rebal_indices)}회')


# -----------------------------------------------------------------------------
# 3. 전략별 결정 + T+20 수익률
# -----------------------------------------------------------------------------
def strategy_choice(i, name):
    """i 시점에서 어떤 지수에 비중을 둘지 결정
    Returns: 'KOSPI', 'KOSDAQ', or 'EQUAL' (50:50)
    """
    if name == 'B1_KOSPI_100':
        return 'KOSPI'
    if name == 'B2_KOSDAQ_100':
        return 'KOSDAQ'
    if name == 'B3_EQUAL':
        return 'EQUAL'
    
    # 지난 20일 수익률
    if i < 20: return 'EQUAL'
    ret_kospi_20 = (kospi_c[i] / kospi_c[i-20] - 1) * 100
    ret_kosdaq_20 = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
    
    if name == 'H1_MOMENTUM':
        return 'KOSPI' if ret_kospi_20 > ret_kosdaq_20 else 'KOSDAQ'
    
    if name == 'H2_REVERSION':
        if i < 60: return 'EQUAL'
        ret_kospi_60 = (kospi_c[i] / kospi_c[i-60] - 1) * 100
        ret_kosdaq_60 = (kosdaq_c[i] / kosdaq_c[i-60] - 1) * 100
        # 60일 덜 오른 쪽 선택
        return 'KOSPI' if ret_kospi_60 < ret_kosdaq_60 else 'KOSDAQ'
    
    if name == 'H3_SPREAD':
        # KOSPI 20d - KOSDAQ 20d > +3%p → KOSDAQ (선호 반전 기대)
        spread = ret_kospi_20 - ret_kosdaq_20
        if spread > 3: return 'KOSDAQ'
        if spread < -3: return 'KOSPI'
        return 'EQUAL'
    
    if name == 'H4_LOW_VOL':
        if i < 20: return 'EQUAL'
        kospi_rets = kospi_c[i-19:i+1] / kospi_c[i-20:i] - 1
        kosdaq_rets = kosdaq_c[i-19:i+1] / kosdaq_c[i-20:i] - 1
        std_kospi = kospi_rets.std()
        std_kosdaq = kosdaq_rets.std()
        return 'KOSPI' if std_kospi < std_kosdaq else 'KOSDAQ'
    
    return 'EQUAL'


def t20_return(i, choice):
    """i 시점에 choice 비중으로 T+20 수익률"""
    if i + 20 >= n: return None
    r_kospi = kospi_c[i+20] / kospi_c[i] - 1
    r_kosdaq = kosdaq_c[i+20] / kosdaq_c[i] - 1
    if choice == 'KOSPI': return r_kospi
    if choice == 'KOSDAQ': return r_kosdaq
    if choice == 'EQUAL': return (r_kospi + r_kosdaq) / 2
    return None


STRATEGIES = [
    'B1_KOSPI_100', 'B2_KOSDAQ_100', 'B3_EQUAL',
    'H1_MOMENTUM', 'H2_REVERSION', 'H3_SPREAD', 'H4_LOW_VOL',
]

print('\n[3/4] 13년 월별 로테이션 시뮬레이션 (각 리밸런싱 T+20 수익 누적)...')
strategy_returns = {}
strategy_choices = {}
for strat in STRATEGIES:
    returns = []
    choices_log = []
    for i in rebal_indices:
        choice = strategy_choice(i, strat)
        ret = t20_return(i, choice)
        if ret is not None:
            returns.append(ret)
            choices_log.append(choice)
    strategy_returns[strat] = np.array(returns)
    strategy_choices[strat] = choices_log
    print(f'  {strat}: {len(returns)}개 리밸런싱')


# -----------------------------------------------------------------------------
# 4. 성과 지표 계산 + 결과 출력
# -----------------------------------------------------------------------------
def compound(rets):
    """수익률 시계열 복리 누적"""
    cum = 1.0
    for r in rets: cum *= (1 + r)
    return cum - 1

def cagr_approx(rets, periods_per_year=12):
    total = compound(rets)
    years = len(rets) / periods_per_year
    if years <= 0 or total <= -1: return 0
    return ((1 + total) ** (1/years) - 1) * 100

def max_drawdown(rets):
    cum = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    return dd.min() * 100

print()
print('=' * 110)
print('[4/4] 13년 월별 로테이션 성과 비교')
print('=' * 110)
print(f'{"전략":<20} {"리밸N":>7} {"누적":>9} {"CAGR":>9} {"MDD":>9} {"Sharpe":>9} '
      f'{"월승률":>7} {"평균":>9} {"std":>8}')
print('-' * 110)

results = {}
for strat in STRATEGIES:
    rets = strategy_returns[strat]
    cum = compound(rets) * 100
    cagr = cagr_approx(rets)
    mdd = max_drawdown(rets)
    win = (rets > 0).mean() * 100
    mean = rets.mean() * 100
    std = rets.std() * 100
    sharpe = mean / std if std > 0 else 0
    
    results[strat] = {
        'cum': cum, 'cagr': cagr, 'mdd': mdd,
        'sharpe': sharpe, 'win': win,
        'mean': mean, 'std': std, 'n': len(rets),
    }
    print(f'{strat:<20} {len(rets):>7} {cum:>+8.1f}% {cagr:>+8.2f}% {mdd:>+8.2f}% '
          f'{sharpe:>9.3f} {win:>6.1f}% {mean:>+8.3f}% {std:>7.3f}%')

# -----------------------------------------------------------------------------
# 5. 벤치마크(B3 EQUAL) 대비 초과 수익
# -----------------------------------------------------------------------------
bench = results['B3_EQUAL']
print()
print('=' * 110)
print(f'벤치마크 (B3_EQUAL) 대비 초과 성과')
print('=' * 110)
print(f'  벤치마크: CAGR {bench["cagr"]:+.2f}%, MDD {bench["mdd"]:+.2f}%, Sharpe {bench["sharpe"]:.3f}')
print()
print(f'{"전략":<20} {"CAGR 차이":>12} {"MDD 차이":>12} {"Sharpe 차이":>13} {"판정":<20}')
print('-' * 110)

for strat in STRATEGIES:
    if strat == 'B3_EQUAL': continue
    r = results[strat]
    cagr_diff = r['cagr'] - bench['cagr']
    mdd_diff = r['mdd'] - bench['mdd']  # 음수일수록 나쁨 → diff 양수면 개선
    sharpe_diff = r['sharpe'] - bench['sharpe']
    
    if cagr_diff > 1.0 and sharpe_diff > 0.05:
        verdict = '✅ 유효 우위'
    elif cagr_diff > 0 and sharpe_diff > 0:
        verdict = '⚠ 약한 우위'
    elif cagr_diff > 0:
        verdict = '참조 (CAGR↑)'
    else:
        verdict = '❌ 열위'
    print(f'{strat:<20} {cagr_diff:>+11.2f}%p {mdd_diff:>+11.2f}%p '
          f'{sharpe_diff:>+12.3f} {verdict:<20}')

# -----------------------------------------------------------------------------
# 6. 전략별 선택 분포
# -----------------------------------------------------------------------------
from collections import Counter
print()
print('=' * 110)
print('전략별 지수 선택 분포 (로테이션 강도 확인)')
print('=' * 110)
print(f'{"전략":<20} {"KOSPI":>10} {"KOSDAQ":>10} {"EQUAL":>10}')
print('-' * 110)
for strat in STRATEGIES:
    c = Counter(strategy_choices[strat])
    total = sum(c.values())
    print(f'{strat:<20} '
          f'{c.get("KOSPI", 0):>6} ({c.get("KOSPI", 0)/total*100:>3.0f}%) '
          f'{c.get("KOSDAQ", 0):>6} ({c.get("KOSDAQ", 0)/total*100:>3.0f}%) '
          f'{c.get("EQUAL", 0):>6} ({c.get("EQUAL", 0)/total*100:>3.0f}%)')

print()
print('완료.')
