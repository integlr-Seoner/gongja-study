"""_v_44_v4_optimal_allocation.py — V4 단독 최적 자본 배분 탐색

배경:
  §32 에서 결합(V4+H3+S2)의 추가 가치 제한적 확인.
  V4 단독이 가장 효율적 — 이제 V4 자본 비중 최적화 필요.

탐색 변수 3개:
  1. V4 전체 비중 (20%~100%, 현금 나머지)
  2. V4 내부 운용 비율 (WORKING_RATIO: 30%/50%/70%)
  3. V4 종목당 한도 (3%/5%/7%)

측정:
  각 조합의 CAGR/MDD/Sharpe/Calmar/월승률/최악연도
  효율적 프론티어 도출
  리스크 허용도별 권고

판정:
  Calmar > 2.0 (CAGR/|MDD|) 이면 투자 가치 명확
  Sharpe > 0.5 이면 단위 위험당 수익 우수
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


print('[1/4] OHLCV 로드...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_idx = {d: i for i, d in enumerate(all_dates)}

# 월별 샘플 (매월 15일 이후 첫 영업일)
samples = []; cy = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        samples.append(d); cy = ym
sample_idx_set = {date_idx[d] for d in samples}
print(f'  샘플: {len(samples)}개월')

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
    """V4 score==4 인 경우 T+1 갭, 아니면 None"""
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


print('\n[2/4] V4 score==4 월별 gap 수집...')
t0 = time.time()
gaps_by_month = defaultdict(list)
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, d_idx in enumerate(dates_col):
        if d_idx not in sample_idx_set: continue
        g = v4_gap(arr, row_pos)
        if g is not None:
            gaps_by_month[all_dates[d_idx]].append(g)
total_n = sum(len(v) for v in gaps_by_month.values())
print(f'  총 {total_n}건 V4=4 발견, 월평균 {total_n/len(samples):.1f}건, {time.time()-t0:.1f}초')


def v4_monthly_return(gaps, v4_total_weight, working_ratio, per_stock, max_pos):
    """월별 V4 전체 자본 기준 수익률
    
    gaps: 해당 월 score==4 종목들의 gap 리스트
    v4_total_weight: 전체 포트폴리오 중 V4 비중 (예: 0.6)
    working_ratio: V4 자본 중 실투입 비율 (예: 0.3)
    per_stock: V4 자본 중 종목당 비율 (예: 0.05)
    max_pos: 최대 포지션 (예: 30)
    
    Returns: 전체 포트폴리오 기준 월 수익률
    """
    if not gaps: return 0.0
    n_stocks = min(len(gaps), max_pos)
    # V4 자본 중 실투입 비율
    invested_pct_v4 = min(n_stocks * per_stock, working_ratio)
    # 평균 realized
    mean_gap = np.mean(gaps[:n_stocks])
    mean_realized = (mean_gap - ROUND_TRIP_COST_PCT) / 100  # decimal
    # 전체 포트폴리오 기준 수익률
    return v4_total_weight * invested_pct_v4 * mean_realized


def stats(rets, ppy=12):
    if len(rets) == 0:
        return {'cagr': 0, 'mdd': 0, 'sharpe': 0, 'calmar': 0, 'win': 0, 'n': 0,
                'mean': 0, 'std': 0, 'worst_year': 0}
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
    # 연도별 최악
    years = defaultdict(list)
    for m, r in zip(month_keys, rets):
        years[m[:4]].append(r)
    yearly_rets = {y: np.prod(1 + np.array(rs)) - 1 for y, rs in years.items()}
    worst = min(yearly_rets.values()) * 100 if yearly_rets else 0
    return {
        'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe, 'calmar': calmar,
        'win': (rets > 0).mean() * 100,
        'mean': mean, 'std': std, 'n': len(rets),
        'worst_year': worst,
    }


month_keys = sorted(gaps_by_month.keys())


# =============================================================================
# [3/4] V4 전체 비중 탐색 (내부 파라미터 고정)
# =============================================================================
print()
print('=' * 105)
print('[3/4] V4 전체 비중 탐색 (운용 30%, 종목당 5%, MAX 30 고정)')
print('=' * 105)
print(f'{"V4 비중":<10} {"현금":<8} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8} '
      f'{"월승률":>8} {"최악연":>10}')
print('-' * 105)

v4_weight_results = {}
for w_v4 in [0.20, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]:
    rets = np.array([
        v4_monthly_return(gaps_by_month[m], w_v4, 0.30, 0.05, 30)
        for m in month_keys
    ])
    s = stats(rets)
    v4_weight_results[w_v4] = s
    tag = ''
    if s['calmar'] > 2.5: tag = ' ⭐'
    print(f'{w_v4*100:.0f}%{"":<6} {(1-w_v4)*100:.0f}%{"":<5} '
          f'{s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% {s["sharpe"]:>8.3f} '
          f'{s["calmar"]:>8.3f} {s["win"]:>7.1f}% {s["worst_year"]:>+9.2f}%{tag}')

# 최적 선택
best_calmar = max(v4_weight_results.items(), key=lambda x: x[1]['calmar'])
best_sharpe = max(v4_weight_results.items(), key=lambda x: x[1]['sharpe'])
print()
print(f'  최고 Calmar: V4 {best_calmar[0]*100:.0f}% (Calmar {best_calmar[1]["calmar"]:.3f})')
print(f'  최고 Sharpe: V4 {best_sharpe[0]*100:.0f}% (Sharpe {best_sharpe[1]["sharpe"]:.3f})')


# =============================================================================
# [4/4] V4 내부 파라미터 민감도 (운용 비율 × 종목당 × MAX)
# =============================================================================
print()
print('=' * 105)
print('[4/4] V4 내부 파라미터 민감도 (V4 비중 100% 고정)')
print('=' * 105)

print()
print('--- 4-A. 운용 비율 민감도 (종목당 5%, MAX 30 고정) ---')
print(f'{"운용%":<8} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8} {"월승률":>8} {"최악연":>10}')
print('-' * 105)
for wr in [0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.80]:
    rets = np.array([
        v4_monthly_return(gaps_by_month[m], 1.0, wr, 0.05, 30)
        for m in month_keys
    ])
    s = stats(rets)
    tag = ' ⭐' if s['calmar'] > 3 else ''
    print(f'{wr*100:.0f}%{"":<4} {s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% '
          f'{s["sharpe"]:>8.3f} {s["calmar"]:>8.3f} {s["win"]:>7.1f}% {s["worst_year"]:>+9.2f}%{tag}')

print()
print('--- 4-B. 종목당 비율 민감도 (운용 30%, MAX 30 고정) ---')
print(f'{"종목당":<8} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8} {"월승률":>8} {"최악연":>10}')
print('-' * 105)
for ps in [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.10]:
    rets = np.array([
        v4_monthly_return(gaps_by_month[m], 1.0, 0.30, ps, 30)
        for m in month_keys
    ])
    s = stats(rets)
    tag = ' ⭐' if s['calmar'] > 3 else ''
    print(f'{ps*100:.1f}%{"":<3} {s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% '
          f'{s["sharpe"]:>8.3f} {s["calmar"]:>8.3f} {s["win"]:>7.1f}% {s["worst_year"]:>+9.2f}%{tag}')

print()
print('--- 4-C. MAX 포지션 민감도 (운용 30%, 종목당 5% 고정) ---')
print(f'{"MAX":<6} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8} {"월승률":>8} {"최악연":>10}')
print('-' * 105)
for mp in [10, 15, 20, 25, 30, 40, 50]:
    rets = np.array([
        v4_monthly_return(gaps_by_month[m], 1.0, 0.30, 0.05, mp)
        for m in month_keys
    ])
    s = stats(rets)
    tag = ' ⭐' if s['calmar'] > 3 else ''
    print(f'{mp:<5} {s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% '
          f'{s["sharpe"]:>8.3f} {s["calmar"]:>8.3f} {s["win"]:>7.1f}% {s["worst_year"]:>+9.2f}%{tag}')


# =============================================================================
# 통합 최적화 — 3차원 그리드
# =============================================================================
print()
print('=' * 105)
print('[통합 최적화] V4 비중 × 운용 비율 × 종목당 (MAX 30 고정)')
print('=' * 105)

best_combos = []
for wv in [0.60, 0.70, 0.80, 1.00]:
    for wr in [0.20, 0.30, 0.50]:
        for ps in [0.03, 0.05, 0.07]:
            rets = np.array([
                v4_monthly_return(gaps_by_month[m], wv, wr, ps, 30)
                for m in month_keys
            ])
            s = stats(rets)
            best_combos.append((wv, wr, ps, s))

# Calmar 순 Top 10
best_combos.sort(key=lambda x: -x[3]['calmar'])
print(f'\nCalmar 상위 10개 조합:')
print(f'{"V4%":<6} {"운용%":<6} {"종목%":<6} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8}')
print('-' * 105)
for wv, wr, ps, s in best_combos[:10]:
    print(f'{wv*100:.0f}%{"":<3} {wr*100:.0f}%{"":<3} {ps*100:.1f}%{"":<2} '
          f'{s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% {s["sharpe"]:>8.3f} {s["calmar"]:>8.3f}')


# =============================================================================
# 리스크 허용도별 권고
# =============================================================================
print()
print('=' * 105)
print('[리스크 허용도별 권고 조합]')
print('=' * 105)

profiles = [
    ('보수 (MDD < -3% 허용)', 3.0),
    ('중립 (MDD < -5% 허용)', 5.0),
    ('공격 (MDD < -8% 허용)', 8.0),
]

for label, mdd_limit in profiles:
    valid = [c for c in best_combos if abs(c[3]['mdd']) <= mdd_limit]
    if valid:
        best = max(valid, key=lambda x: x[3]['cagr'])
        wv, wr, ps, s = best
        print(f'\n  {label}:')
        print(f'    V4 비중: {wv*100:.0f}% / 운용: {wr*100:.0f}% / 종목당: {ps*100:.1f}%')
        print(f'    CAGR {s["cagr"]:+.2f}%, MDD {s["mdd"]:+.2f}%, '
              f'Sharpe {s["sharpe"]:.3f}, Calmar {s["calmar"]:.3f}')
        print(f'    월승률 {s["win"]:.1f}%, 최악 연도 {s["worst_year"]:+.2f}%')
    else:
        print(f'\n  {label}: 조건 만족 조합 없음 (더 보수적 필요)')


# =============================================================================
# 벤치마크 비교 (KOSPI 단순 보유)
# =============================================================================
print()
print('=' * 105)
print('[벤치마크 비교]')
print('=' * 105)

# KOSPI 월별 수익 (같은 샘플일 사용)
conn2 = sqlite3.connect(DB, timeout=30)
kospi_rows = conn2.execute(
    "SELECT date, close FROM daily_index_long WHERE symbol='KOSPI' "
    "AND date >= '20140101' ORDER BY date"
).fetchall()
conn2.close()
kospi_dict = {d: c for d, c in kospi_rows}
kospi_dates = sorted(kospi_dict.keys())

kospi_monthly = []
for m in month_keys:
    # 해당 월의 15일 이후 첫 영업일
    for d in all_dates:
        if d[:6] == m[:6] and int(d[6:]) >= 15 and d in kospi_dict:
            i = kospi_dates.index(d) if d in kospi_dates else -1
            if i >= 0 and i + 20 < len(kospi_dates):
                d20 = kospi_dates[i+20]
                r = kospi_dict[d20] / kospi_dict[d] - 1
                kospi_monthly.append(r)
                break
    else:
        kospi_monthly.append(0)
kospi_monthly = np.array(kospi_monthly)
ks = stats(kospi_monthly)

print(f'{"벤치":<35} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"Calmar":>8}')
print('-' * 105)
print(f'{"KOSPI 100%":<35} {ks["cagr"]:>+8.2f}% {ks["mdd"]:>+8.2f}% '
      f'{ks["sharpe"]:>8.3f} {ks["calmar"]:>8.3f}')

# 대표 V4 구성 비교
for wv, wr, ps, label in [(1.0, 0.30, 0.05, 'V4 100% 표준'),
                            (0.60, 0.50, 0.07, 'V4 60%+현금 공격'),
                            (0.40, 0.30, 0.05, 'V4 40%+현금 보수')]:
    rets = np.array([
        v4_monthly_return(gaps_by_month[m], wv, wr, ps, 30)
        for m in month_keys
    ])
    s = stats(rets)
    print(f'{label:<35} {s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% '
          f'{s["sharpe"]:>8.3f} {s["calmar"]:>8.3f}')

print()
print('완료.')
