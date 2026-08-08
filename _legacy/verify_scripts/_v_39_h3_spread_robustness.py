"""_v_39_h3_spread_robustness.py — H3 SPREAD 전략 견고성 검증

목적:
  _v_38 에서 발견한 H3 SPREAD (CAGR +11.01%) 의 견고성을 5의혹 검증으로 확정.

의혹 5가지:
  ⚠1 시기 편향 — 3기간 (P1/P2/P3) 나눠 확인
  ⚠2 임계값 과적합 — ±1~7%p 민감도 분석
  ⚠3 리밸런싱 주기 의존 — 주/월/분기 비교
  ⚠4 레짐 의존 — BULL/SIDEWAYS/BEAR 분해
  ⚠5 극단치 의존 — 상위 5건 제거 후 결과

판정: 각 의혹별 기각 여부 명확히 출력
"""
import sqlite3
import numpy as np
from collections import Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/6] KOSPI / KOSDAQ 로드...')
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
kospi_c = np.array([kospi_dict[d] for d in common_dates])
kosdaq_c = np.array([kosdaq_dict[d] for d in common_dates])
dates = np.array(common_dates)
n = len(common_dates)
print(f'  거래일: {n:,}')


def rebal_indices(freq, holding_days=None):
    """리밸런싱 시점 + 각 시점의 보유 기간"""
    if freq == 'weekly':
        hd = holding_days or 5
        step = 5
        pts = list(range(0, n, step))
    elif freq == 'monthly':
        hd = holding_days or 20
        pts = []
        cy = ''
        for i, d in enumerate(common_dates):
            ym, dd = d[:6], int(d[6:8])
            if ym != cy and dd >= 15:
                pts.append(i); cy = ym
    elif freq == 'quarterly':
        hd = holding_days or 60
        pts = []
        cy_q = ''
        for i, d in enumerate(common_dates):
            y, m = int(d[:4]), int(d[4:6])
            q = (m - 1) // 3
            yq = f'{y}Q{q}'
            if yq != cy_q and int(d[6:8]) >= 15:
                pts.append(i); cy_q = yq
    pts = [p for p in pts if p + hd < n and p >= 20]
    return pts, hd


def run_h3(rebal_pts, holding_days, threshold):
    """H3 SPREAD: KOSPI 20d - KOSDAQ 20d > threshold → KOSDAQ
                 -threshold 미만 → KOSPI
                 그 외 → EQUAL
    Returns: returns list, choices list, dates list
    """
    rets = []; choices = []; pt_dates = []
    for i in rebal_pts:
        if i < 20: continue
        ret_k = (kospi_c[i] / kospi_c[i-20] - 1) * 100
        ret_q = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
        spread = ret_k - ret_q
        
        if spread > threshold:
            choice = 'KOSDAQ'
        elif spread < -threshold:
            choice = 'KOSPI'
        else:
            choice = 'EQUAL'
        
        # 보유 기간 수익
        r_kospi = kospi_c[i+holding_days] / kospi_c[i] - 1
        r_kosdaq = kosdaq_c[i+holding_days] / kosdaq_c[i] - 1
        if choice == 'KOSPI': r = r_kospi
        elif choice == 'KOSDAQ': r = r_kosdaq
        else: r = (r_kospi + r_kosdaq) / 2
        
        rets.append(r); choices.append(choice); pt_dates.append(common_dates[i])
    return np.array(rets), choices, pt_dates


def run_equal(rebal_pts, holding_days):
    """벤치마크: EQUAL 50:50"""
    rets = []
    for i in rebal_pts:
        r_kospi = kospi_c[i+holding_days] / kospi_c[i] - 1
        r_kosdaq = kosdaq_c[i+holding_days] / kosdaq_c[i] - 1
        rets.append((r_kospi + r_kosdaq) / 2)
    return np.array(rets)


def stats(rets, periods_per_year=12):
    """성과 지표"""
    if len(rets) == 0:
        return {'cum': 0, 'cagr': 0, 'mdd': 0, 'sharpe': 0, 'win': 0, 'n': 0}
    cum = np.prod(1 + rets) - 1
    years = len(rets) / periods_per_year
    cagr = ((1 + cum) ** (1/years) - 1) * 100 if years > 0 and cum > -1 else 0
    cum_prod = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cum_prod)
    dd = (cum_prod - peak) / peak
    mdd = dd.min() * 100
    mean = rets.mean() * 100
    std = rets.std() * 100
    sharpe = mean / std if std > 0 else 0
    win = (rets > 0).mean() * 100
    return {'cum': cum * 100, 'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe,
            'win': win, 'mean': mean, 'std': std, 'n': len(rets)}


# =============================================================================
# [2/6] ⚠1 시기 편향 — P1/P2/P3 나눠 확인
# =============================================================================
print()
print('=' * 100)
print('[2/6] ⚠1 시기 편향 검증 — 3기간 (P1/P2/P3)')
print('=' * 100)

PERIODS = {
    'P1 (2014~2018)': ('20140101', '20181231'),
    'P2 (2019~2022)': ('20190101', '20221231'),
    'P3 (2023~2026)': ('20230101', '20261231'),
}

month_pts, hd_month = rebal_indices('monthly')
h3_rets, h3_ch, h3_dates = run_h3(month_pts, hd_month, threshold=3.0)
bench_rets = run_equal(month_pts, hd_month)

print(f'{"기간":<18} {"H3 N":>6} {"H3 CAGR":>10} {"H3 MDD":>10} {"벤치 CAGR":>10} {"벤치 MDD":>10} '
      f'{"차이":>8} {"판정":<12}')
print('-' * 100)

bias_results = []
for label, (start, end) in PERIODS.items():
    # 해당 기간의 인덱스만 선별
    mask = [(d >= start and d <= end) for d in h3_dates]
    h3_sub = h3_rets[mask]
    bench_sub = bench_rets[mask]
    h3_s = stats(h3_sub)
    bench_s = stats(bench_sub)
    cagr_diff = h3_s['cagr'] - bench_s['cagr']
    verdict = '✅ 우위' if cagr_diff > 0.5 else ('⚠ 약' if cagr_diff > 0 else '❌ 열위')
    print(f'{label:<18} {h3_s["n"]:>6} {h3_s["cagr"]:>+9.2f}% {h3_s["mdd"]:>+9.2f}% '
          f'{bench_s["cagr"]:>+9.2f}% {bench_s["mdd"]:>+9.2f}% '
          f'{cagr_diff:>+7.2f}%p {verdict:<12}')
    bias_results.append((label, cagr_diff))

all_period_positive = all(d > 0 for _, d in bias_results)
print()
print(f'  ⚠1 기각 여부: {"✅ 기각 (모든 기간 우위)" if all_period_positive else "⚠ 부분 의혹 (일부 기간 열위)"}')


# =============================================================================
# [3/6] ⚠2 임계값 과적합 — ±1~7%p 민감도
# =============================================================================
print()
print('=' * 100)
print('[3/6] ⚠2 임계값 과적합 검증 — ±1~7%p 민감도')
print('=' * 100)

bench_s = stats(bench_rets)
print(f'  벤치마크 (EQUAL): CAGR {bench_s["cagr"]:+.2f}%, Sharpe {bench_s["sharpe"]:.3f}')
print()
print(f'{"임계값":>8} {"H3 CAGR":>10} {"CAGR 차이":>11} {"MDD":>10} {"Sharpe":>9} '
      f'{"승률":>7} {"판정":<12}')
print('-' * 100)

thresh_results = []
for th in [1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 7.0]:
    r, _, _ = run_h3(month_pts, hd_month, threshold=th)
    s = stats(r)
    diff = s['cagr'] - bench_s['cagr']
    verdict = '✅' if diff > 1.0 else ('⚠' if diff > 0 else '❌')
    print(f'±{th:>4.1f}%p {s["cagr"]:>+9.2f}% {diff:>+10.2f}%p {s["mdd"]:>+9.2f}% '
          f'{s["sharpe"]:>9.3f} {s["win"]:>6.1f}% {verdict:<12}')
    thresh_results.append((th, diff))

# ±2~5%p 범위 안정성
stable_range = [d for t, d in thresh_results if 2.0 <= t <= 5.0]
stable_ok = all(d > 0 for d in stable_range)
min_diff = min(stable_range) if stable_range else 0
print()
print(f'  ±2~5%p 범위 안정성: 최저 차이 {min_diff:+.2f}%p')
print(f'  ⚠2 기각 여부: {"✅ 기각 (범위 안정)" if stable_ok and min_diff > 0.5 else "⚠ 부분 의혹"}')

# =============================================================================
# [4/6] ⚠3 리밸런싱 주기 — 주/월/분기
# =============================================================================
print()
print('=' * 100)
print('[4/6] ⚠3 리밸런싱 주기 의존 검증 — 주/월/분기')
print('=' * 100)

print(f'{"주기":<12} {"N":>6} {"H3 CAGR":>10} {"벤치 CAGR":>10} {"차이":>9} {"H3 Sharpe":>10} {"판정":<12}')
print('-' * 100)

period_per_year = {'weekly': 50, 'monthly': 12, 'quarterly': 4}
freq_results = []
for freq in ['weekly', 'monthly', 'quarterly']:
    pts, hd = rebal_indices(freq)
    h3_r, _, _ = run_h3(pts, hd, threshold=3.0)
    bench_r = run_equal(pts, hd)
    ppy = period_per_year[freq]
    h3_s = stats(h3_r, periods_per_year=ppy)
    bench_s_freq = stats(bench_r, periods_per_year=ppy)
    diff = h3_s['cagr'] - bench_s_freq['cagr']
    verdict = '✅ 우위' if diff > 0.5 else ('⚠ 약' if diff > 0 else '❌ 열위')
    print(f'{freq:<12} {h3_s["n"]:>6} {h3_s["cagr"]:>+9.2f}% {bench_s_freq["cagr"]:>+9.2f}% '
          f'{diff:>+8.2f}%p {h3_s["sharpe"]:>9.3f} {verdict:<12}')
    freq_results.append((freq, diff))

all_freq_ok = all(d > 0 for _, d in freq_results)
print()
print(f'  ⚠3 기각 여부: {"✅ 기각 (모든 주기 우위)" if all_freq_ok else "⚠ 부분 의혹 (특정 주기 의존)"}')


# =============================================================================
# [5/6] ⚠4 레짐 의존 — BULL/SIDEWAYS/BEAR 분해
# =============================================================================
print()
print('=' * 100)
print('[5/6] ⚠4 레짐 의존 검증 — 리밸런싱 시점의 레짐별 결과')
print('=' * 100)

def classify_regime_at(i):
    """리밸런싱 시점의 KOSPI 20일 수익률 기반 레짐"""
    if i < 20: return None
    ret = (kospi_c[i] / kospi_c[i-20] - 1) * 100
    if ret >= 5: return 'BULL'
    elif ret <= -5: return 'BEAR'
    else: return 'SIDEWAYS'

# 월 리밸런싱 기준, 각 포인트별 레짐 매핑
point_regimes = [classify_regime_at(i) for i in month_pts]

h3_by_regime = {}
bench_by_regime = {}
for idx, rg in enumerate(point_regimes):
    if rg is None: continue
    h3_by_regime.setdefault(rg, []).append(h3_rets[idx])
    bench_by_regime.setdefault(rg, []).append(bench_rets[idx])

print(f'{"레짐":<12} {"N":>5} {"H3 평균":>10} {"벤치 평균":>10} {"차이":>8} {"H3 승률":>8} {"판정":<15}')
print('-' * 100)

regime_results = []
for rg in ['BULL', 'SIDEWAYS', 'BEAR']:
    if rg not in h3_by_regime:
        print(f'{rg:<12} (N=0)'); continue
    h3_arr = np.array(h3_by_regime[rg]) * 100
    bench_arr = np.array(bench_by_regime[rg]) * 100
    diff = h3_arr.mean() - bench_arr.mean()
    win = (h3_arr > 0).mean() * 100
    verdict = '✅ 우위' if diff > 0.2 else ('⚠ 약' if diff > 0 else '❌ 열위')
    print(f'{rg:<12} {len(h3_arr):>5} {h3_arr.mean():>+9.3f}% {bench_arr.mean():>+9.3f}% '
          f'{diff:>+7.3f}%p {win:>7.1f}% {verdict:<15}')
    regime_results.append((rg, diff))

# 최소 2/3 레짐 우위
positive_count = sum(1 for _, d in regime_results if d > 0)
print()
print(f'  ⚠4 기각 여부: {"✅ 기각" if positive_count >= 2 else "⚠ 부분 의혹"} '
      f'({positive_count}/{len(regime_results)} 레짐 우위)')

# =============================================================================
# [6/6] ⚠5 극단치 의존 — 상위 5건 제거
# =============================================================================
print()
print('=' * 100)
print('[6/6] ⚠5 극단치 의존 검증 — 상위/하위 극단치 제거')
print('=' * 100)

h3_sorted = np.sort(h3_rets)[::-1]  # 내림차순
print(f'  원본 H3: N={len(h3_rets)}, CAGR {stats(h3_rets)["cagr"]:+.2f}%')
print(f'  상위 3건: {[f"{r*100:+.2f}%" for r in h3_sorted[:3]]}')
print(f'  하위 3건: {[f"{r*100:+.2f}%" for r in h3_sorted[-3:]]}')
print()

for n_ex in [3, 5, 10]:
    h3_ex = h3_rets[np.argsort(h3_rets)[n_ex:-n_ex]] if n_ex*2 < len(h3_rets) else h3_rets
    bench_ex = bench_rets[np.argsort(h3_rets)[n_ex:-n_ex]] if n_ex*2 < len(h3_rets) else bench_rets
    h3_s = stats(h3_ex)
    bench_s_ex = stats(bench_ex)
    diff = h3_s['cagr'] - bench_s_ex['cagr']
    verdict = '✅ 유지' if diff > 0.5 else ('⚠ 약' if diff > 0 else '❌ 소실')
    print(f'  상하위 {n_ex}건씩 제거 (N={len(h3_ex)}): '
          f'H3 CAGR {h3_s["cagr"]:+.2f}% vs 벤치 {bench_s_ex["cagr"]:+.2f}% '
          f'(차이 {diff:+.2f}%p) → {verdict}')

# 상위 5건 제거해도 우위 유지 여부
h3_no_top5 = h3_rets[np.argsort(h3_rets)[:-5]]
bench_no_top5 = bench_rets[np.argsort(h3_rets)[:-5]]
h3_s = stats(h3_no_top5)
bench_s_ex = stats(bench_no_top5)
diff_no_top5 = h3_s['cagr'] - bench_s_ex['cagr']
print()
print(f'  상위 5건만 제거 (N={len(h3_no_top5)}): '
      f'차이 {diff_no_top5:+.2f}%p')
print(f'  ⚠5 기각 여부: {"✅ 기각 (극단치 제거 후에도 우위)" if diff_no_top5 > 0.5 else "⚠ 부분 의혹"}')

# =============================================================================
# 최종 판정
# =============================================================================
print()
print('=' * 100)
print('최종 판정 — H3 SPREAD 5의혹 검증')
print('=' * 100)
print(f'  ⚠1 시기 편향:    {"✅ 기각" if all_period_positive else "⚠ 부분"}')
print(f'  ⚠2 임계값 과적합: {"✅ 기각" if stable_ok and min_diff > 0.5 else "⚠ 부분"}')
print(f'  ⚠3 주기 의존:    {"✅ 기각" if all_freq_ok else "⚠ 부분"}')
print(f'  ⚠4 레짐 의존:    {"✅ 기각" if positive_count >= 2 else "⚠ 부분"} ({positive_count}/{len(regime_results)})')
print(f'  ⚠5 극단치 의존:  {"✅ 기각" if diff_no_top5 > 0.5 else "⚠ 부분"}')
print()
print('완료.')
