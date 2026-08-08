"""_v_45_v4_dynamic_regime_params.py — V4 레짐별 동적 파라미터

배경:
  §23: V4 는 BULL/SIDEWAYS/BEAR 모두 양수이지만 강도 다름
  §33: V4 최적 파라미터 확정 (종목당 7%, 운용 30%)
  결합: 레짐별 파라미터 동적 조정 시 추가 개선?

가설:
  BULL   → 공격 (운용↑, 종목↑) — 승률 낮지만 수익 큼
  SIDEWAYS → 균형 (운용 30%, 종목 7%)
  BEAR   → 방어 (운용↓, 종목↓) — 승률 높지만 수익 낮음

동적 3안:
  안1 공격: BULL(50/10) / SIDEWAYS(30/7) / BEAR(15/5)
  안2 균형: BULL(40/8)  / SIDEWAYS(30/7) / BEAR(20/5)
  안3 방어: BULL(30/7)  / SIDEWAYS(30/7) / BEAR(10/4)

비교 기준: 정적 (30/7) — §33 최적
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

print('[1/4] KOSPI 지수 + 레짐 분류...')
kospi_rows = cur.execute(
    "SELECT date, close FROM daily_index_long WHERE symbol='KOSPI' "
    "AND date >= '20140101' ORDER BY date"
).fetchall()
kospi_dates = [r[0] for r in kospi_rows]
kospi_closes = np.array([r[1] for r in kospi_rows])

def regime_of(date_str):
    """KOSPI 20일 수익률 기반"""
    if date_str not in kospi_dates: return None
    i = kospi_dates.index(date_str)
    if i < 20: return None
    ret = (kospi_closes[i] / kospi_closes[i-20] - 1) * 100
    if ret >= 5: return 'BULL'
    elif ret <= -5: return 'BEAR'
    else: return 'SIDEWAYS'

print('[2/4] OHLCV 로드 + 월별 V4 gap 수집...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_idx = {d: i for i, d in enumerate(all_dates)}

samples = []; cy = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        samples.append(d); cy = ym
sample_idx_set = {date_idx[d] for d in samples}

t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_idx.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  OHLCV: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def v4_gap(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    close_t = c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    ma5 = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - o[t_pos]; rng = h[t_pos] - lo[t_pos]
    cond1 = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    cond2 = h[t_pos] > h[t_pos-60:t_pos].max()
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    cond3 = tv_arr.mean() > 0 and (close_t * vol_t / tv_arr.mean() >= 3.0)
    cond4 = (rng > 0) and ((close_t - lo[t_pos]) / rng >= 0.95)
    score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    if score != 4: return None
    return (open_t1 / close_t - 1) * 100


gaps_by_month = defaultdict(list)
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, d_idx in enumerate(dates_col):
        if d_idx not in sample_idx_set: continue
        g = v4_gap(arr, row_pos)
        if g is not None:
            gaps_by_month[all_dates[d_idx]].append(g)

# 월별 레짐 분류
regime_by_month = {m: regime_of(m) for m in samples}
regime_counter = defaultdict(int)
for m, r in regime_by_month.items():
    if r: regime_counter[r] += 1
print(f'  V4=4 월별 수집 완료')
print(f'  샘플 레짐 분포: BULL {regime_counter["BULL"]} / '
      f'SIDEWAYS {regime_counter["SIDEWAYS"]} / BEAR {regime_counter["BEAR"]}')


def monthly_return_with_params(gaps, working_ratio, per_stock, max_pos=30):
    """주어진 파라미터로 월 수익 (V4 전량 투자 가정)"""
    if not gaps: return 0.0
    n_stocks = min(len(gaps), max_pos)
    invested_pct = min(n_stocks * per_stock, working_ratio)
    mean_gap = np.mean(gaps[:n_stocks])
    mean_realized = (mean_gap - ROUND_TRIP_COST_PCT) / 100
    return invested_pct * mean_realized


def stats(rets, ppy=12):
    if len(rets) == 0:
        return {'cagr': 0, 'mdd': 0, 'sharpe': 0, 'calmar': 0, 'win': 0, 'n': 0,
                'mean': 0, 'std': 0}
    cum = np.prod(1 + rets) - 1
    yrs = len(rets) / ppy
    cagr = ((1 + cum) ** (1/yrs) - 1) * 100 if yrs > 0 and cum > -1 else 0
    cp = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cp)
    dd = (cp - peak) / peak
    mdd = dd.min() * 100
    mean = rets.mean() * 100
    std = rets.std() * 100
    sharpe = mean / std if std > 0 else 0
    calmar = cagr / abs(mdd) if mdd < 0 else 0
    return {'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe, 'calmar': calmar,
            'win': (rets > 0).mean() * 100, 'mean': mean, 'std': std, 'n': len(rets)}


# =============================================================================
# [3/4] 정적 vs 동적 비교
# =============================================================================
print()
print('=' * 100)
print('[3/4] 정적 (기준) vs 동적 파라미터 3안 비교')
print('=' * 100)

month_keys = sorted(gaps_by_month.keys() | set(samples))

# 정적: 종목당 7% + 운용 30% (§33 최적)
static_rets = np.array([
    monthly_return_with_params(gaps_by_month.get(m, []), 0.30, 0.07)
    for m in samples
])

# 동적 3안 정의
DYNAMIC_PLANS = {
    '안1 공격 (BULL 50/10, SIDE 30/7, BEAR 15/5)': {
        'BULL': (0.50, 0.10), 'SIDEWAYS': (0.30, 0.07), 'BEAR': (0.15, 0.05)
    },
    '안2 균형 (BULL 40/8,  SIDE 30/7, BEAR 20/5)': {
        'BULL': (0.40, 0.08), 'SIDEWAYS': (0.30, 0.07), 'BEAR': (0.20, 0.05)
    },
    '안3 방어 (BULL 30/7,  SIDE 30/7, BEAR 10/4)': {
        'BULL': (0.30, 0.07), 'SIDEWAYS': (0.30, 0.07), 'BEAR': (0.10, 0.04)
    },
    '안4 보수공격 (BULL 50/10, SIDE 30/7, BEAR 10/4)': {
        'BULL': (0.50, 0.10), 'SIDEWAYS': (0.30, 0.07), 'BEAR': (0.10, 0.04)
    },
}

def run_dynamic(plan):
    rets = []
    for m in samples:
        rg = regime_by_month.get(m)
        if rg is None:
            # 레짐 분류 실패 → 기본값 (SIDEWAYS)
            wr, ps = plan['SIDEWAYS']
        else:
            wr, ps = plan[rg]
        rets.append(monthly_return_with_params(gaps_by_month.get(m, []), wr, ps))
    return np.array(rets)


print(f'{"전략":<55} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8} {"월승률":>8}')
print('-' * 110)

static_s = stats(static_rets)
print(f'{"정적 기준 (운용 30%, 종목 7%)":<55} '
      f'{static_s["cagr"]:>+8.2f}% {static_s["mdd"]:>+8.2f}% '
      f'{static_s["sharpe"]:>8.3f} {static_s["calmar"]:>8.3f} {static_s["win"]:>7.1f}%')
print('-' * 110)

dynamic_results = {}
for label, plan in DYNAMIC_PLANS.items():
    rets = run_dynamic(plan)
    s = stats(rets)
    dynamic_results[label] = s
    cagr_diff = s['cagr'] - static_s['cagr']
    mdd_diff = s['mdd'] - static_s['mdd']
    tag = ' ⭐' if (cagr_diff > 0.5 and mdd_diff >= 0) else ('' if cagr_diff > 0 else ' ↓')
    print(f'{label:<55} '
          f'{s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% '
          f'{s["sharpe"]:>8.3f} {s["calmar"]:>8.3f} {s["win"]:>7.1f}%{tag}')


# =============================================================================
# [4/4] 최강 안의 레짐별 분해 — 어디서 이득/손실 발생?
# =============================================================================
print()
print('=' * 100)
print('[4/4] 레짐별 기여 분해')
print('=' * 100)

def period_stats_by_regime(rets):
    """레짐별 평균 수익 + 월수"""
    by_rg = defaultdict(list)
    for m, r in zip(samples, rets):
        rg = regime_by_month.get(m)
        if rg: by_rg[rg].append(r)
    return {rg: stats(np.array(rs)) for rg, rs in by_rg.items()}

# 정적 vs 최강 동적 안 비교
best_label = max(dynamic_results.items(), key=lambda x: x[1]['cagr'])[0]
best_plan = DYNAMIC_PLANS[best_label]
best_rets = run_dynamic(best_plan)

static_by_rg = period_stats_by_regime(static_rets)
best_by_rg = period_stats_by_regime(best_rets)

print(f'\n최강 동적 안: {best_label}')
print()
print(f'{"레짐":<12} {"N":>5} {"정적 CAGR":>11} {"동적 CAGR":>11} '
      f'{"정적 MDD":>11} {"동적 MDD":>11} {"동적 월평균":>13}')
print('-' * 110)
for rg in ['BULL', 'SIDEWAYS', 'BEAR']:
    if rg not in static_by_rg: continue
    ss = static_by_rg[rg]
    bs = best_by_rg[rg]
    print(f'{rg:<12} {bs["n"]:>5} {ss["cagr"]:>+10.2f}% {bs["cagr"]:>+10.2f}% '
          f'{ss["mdd"]:>+10.2f}% {bs["mdd"]:>+10.2f}% {bs["mean"]:>+12.3f}%')


# =============================================================================
# 추가: 전환기 비용 (레짐 변경 시점) 분석
# =============================================================================
print()
print('=' * 100)
print('[추가] 레짐 전환기 — 레짐 변경 후 첫 달 수익')
print('=' * 100)

# 월별 레짐 시퀀스
regime_seq = [regime_by_month.get(m) for m in samples]
transitions = []  # (month_idx, prev_regime, new_regime, static_ret, dynamic_ret)
for i in range(1, len(samples)):
    prev = regime_seq[i-1]
    curr = regime_seq[i]
    if prev is None or curr is None: continue
    if prev != curr:
        transitions.append({
            'month': samples[i], 'prev': prev, 'curr': curr,
            'static': static_rets[i] * 100, 'dynamic': best_rets[i] * 100,
        })

if transitions:
    print(f'\n  총 {len(transitions)}회 레짐 전환')
    static_avg = np.mean([t['static'] for t in transitions])
    dynamic_avg = np.mean([t['dynamic'] for t in transitions])
    print(f'  전환기 월평균 수익: 정적 {static_avg:+.3f}%, 동적 {dynamic_avg:+.3f}%')
    print(f'  동적이 전환기에 {"유리" if dynamic_avg > static_avg else "불리"}')
else:
    print('  레짐 전환 없음')


# =============================================================================
# 결론 + 운영 권고
# =============================================================================
print()
print('=' * 100)
print('결론')
print('=' * 100)

static_cagr = static_s['cagr']
static_mdd = static_s['mdd']

print(f'\n  정적 기준: CAGR {static_cagr:+.2f}%, MDD {static_mdd:+.2f}%, '
      f'Calmar {static_s["calmar"]:.3f}')
print()

improvement_count = 0
for label, s in dynamic_results.items():
    cagr_d = s['cagr'] - static_cagr
    mdd_d = s['mdd'] - static_mdd
    label_short = label.split(' ')[0] + ' ' + label.split(' ')[1]
    
    if cagr_d > 0.3 and mdd_d >= -0.5:
        verdict = '✅ 명확한 개선'
        improvement_count += 1
    elif cagr_d > 0 and mdd_d > -0.1:
        verdict = '⚠ 미세 개선'
    elif cagr_d <= 0:
        verdict = '❌ 열위'
    else:
        verdict = '➖ 트레이드오프'
    print(f'  {label_short}: CAGR {cagr_d:+.2f}%p, MDD {mdd_d:+.2f}%p → {verdict}')

print()
if improvement_count >= 1:
    print('  ✅ 동적 파라미터 적용 가치 있음')
else:
    print('  ❌ 정적 파라미터 유지가 최선 (동적 조정 가치 제한적)')

print()
print('완료.')
