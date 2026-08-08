"""_v_42_h3_s2_robustness.py — H3+S2 견고성 재검증

배경:
  _v_41 에서 cd=60, th=0.80 이 최강 조합 판정 (P3 차이 +4.53%p).
  이것이 우연의 피크인지, 진짜 강건한 파라미터인지 확인 필수.

5의혹 검증:
  ⚠1 파라미터 과적합 — 인접값 스트레스 테스트
  ⚠2 리밸런싱 주기 — 주/월/분기 S2 효과 비교
  ⚠3 시기 편향 — P1/P2/P3 개별 S2 효과
  ⚠4 극단치 의존 — 상/하위 제거 후 유지?
  ⚠5 우연의 피크 — 인근 조합과 성과 유사?
"""
import sqlite3
import numpy as np
from collections import Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()
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
n = len(common_dates)

PERIODS = {
    'P1 (14~18)': ('20140101', '20181231'),
    'P2 (19~22)': ('20190101', '20221231'),
    'P3 (23~26)': ('20230101', '20261231'),
}


def get_rebal_pts(freq, min_idx=60):
    """리밸런싱 시점 (필터 상관계수 60일 필요)"""
    if freq == 'weekly':
        step = 5; pts = list(range(min_idx, n, step)); hd = 5
    elif freq == 'monthly':
        pts = []; cy = ''
        for i, d in enumerate(common_dates):
            ym, dd = d[:6], int(d[6:8])
            if ym != cy and dd >= 15:
                pts.append(i); cy = ym
        hd = 20
    elif freq == 'quarterly':
        pts = []; cy_q = ''
        for i, d in enumerate(common_dates):
            y, m = int(d[:4]), int(d[4:6])
            q = (m - 1) // 3
            yq = f'{y}Q{q}'
            if yq != cy_q and int(d[6:8]) >= 15:
                pts.append(i); cy_q = yq
        hd = 60
    return [p for p in pts if p >= min_idx and p + hd < n], hd


def rolling_corr(i, days):
    if i < days: return None
    k_slice = kospi_c[i-days:i+1]
    q_slice = kosdaq_c[i-days:i+1]
    k_rets = np.diff(k_slice) / k_slice[:-1]
    q_rets = np.diff(q_slice) / q_slice[:-1]
    if k_rets.std() == 0 or q_rets.std() == 0: return None
    return float(np.corrcoef(k_rets, q_rets)[0, 1])


def run_h3_s2(pts, hd, corr_days, corr_th, spread_th=3.0):
    rets = []; choices = []; pt_dates = []
    for i in pts:
        corr = rolling_corr(i, corr_days)
        if corr is not None and corr > corr_th:
            choice = 'EQUAL'
        else:
            k20 = (kospi_c[i] / kospi_c[i-20] - 1) * 100
            q20 = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
            sp = k20 - q20
            if sp > spread_th: choice = 'KOSDAQ'
            elif sp < -spread_th: choice = 'KOSPI'
            else: choice = 'EQUAL'
        r_k = kospi_c[i+hd] / kospi_c[i] - 1
        r_q = kosdaq_c[i+hd] / kosdaq_c[i] - 1
        if choice == 'KOSPI': r = r_k
        elif choice == 'KOSDAQ': r = r_q
        else: r = (r_k + r_q) / 2
        rets.append(r); choices.append(choice); pt_dates.append(common_dates[i])
    return np.array(rets), choices, pt_dates


def run_bench(pts, hd):
    rets = []
    for i in pts:
        r_k = kospi_c[i+hd] / kospi_c[i] - 1
        r_q = kosdaq_c[i+hd] / kosdaq_c[i] - 1
        rets.append((r_k + r_q) / 2)
    return np.array(rets)


def stats(rets, ppy=12):
    if len(rets) == 0:
        return {'cagr': 0, 'mdd': 0, 'sharpe': 0, 'n': 0, 'mean': 0, 'std': 0}
    cum = np.prod(1 + rets) - 1
    yrs = len(rets) / ppy
    cagr = ((1 + cum) ** (1/yrs) - 1) * 100 if yrs > 0 and cum > -1 else 0
    cp = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cp)
    dd = (cp - peak) / peak
    return {
        'cagr': cagr, 'mdd': dd.min() * 100,
        'sharpe': (rets.mean() * 100) / (rets.std() * 100) if rets.std() > 0 else 0,
        'n': len(rets), 'mean': rets.mean() * 100, 'std': rets.std() * 100,
    }


# =============================================================================
# 기준값 + 월별 리밸런싱
# =============================================================================
month_pts, hd = get_rebal_pts('monthly')
print(f'월별 리밸런싱 시점: {len(month_pts)}회')

# 원본 H3+S2 (cd=60, th=0.80)
base_rets, _, base_dates = run_h3_s2(month_pts, hd, 60, 0.80)
base_bench = run_bench(month_pts, hd)
base_s = stats(base_rets)
bench_s = stats(base_bench)
print(f'\n기준: H3+S2 (cd=60, th=0.80)')
print(f'  CAGR {base_s["cagr"]:+.2f}%, MDD {base_s["mdd"]:+.2f}%, Sharpe {base_s["sharpe"]:.3f}')
print(f'  벤치 CAGR {bench_s["cagr"]:+.2f}% (차이 +{base_s["cagr"]-bench_s["cagr"]:.2f}%p)')


# =============================================================================
# ⚠1 파라미터 과적합 — cd, th 민감도 스트레스 테스트
# =============================================================================
print()
print('=' * 100)
print('[⚠1] 파라미터 과적합 검증 — cd × th 인근값 스트레스 테스트')
print('=' * 100)

# cd 주변값 (50, 55, 60, 65, 70) × th 주변값 (0.75, 0.78, 0.80, 0.82, 0.85)
CD_GRID = [50, 55, 60, 65, 70]
TH_GRID = [0.75, 0.78, 0.80, 0.82, 0.85]

print(f'  {"":>5}', end='')
for th in TH_GRID: print(f' th={th:<5.2f}', end='')
print(f'   {"평균":>7}')
print('-' * 100)

cd_results = {}
for cd in CD_GRID:
    row = []
    print(f'  cd={cd:<3}', end='')
    for th in TH_GRID:
        r, _, _ = run_h3_s2(month_pts, hd, cd, th)
        s = stats(r)
        diff = s['cagr'] - bench_s['cagr']
        row.append(diff)
        cd_results[(cd, th)] = s
        print(f' {diff:>+6.2f}%p', end='')
    avg = np.mean(row)
    print(f'  {avg:>+6.2f}%p')

# 견고성 판정: 인근 25개 조합 중 몇 개가 벤치 대비 +2.5%p 초과?
good_count = sum(1 for (cd, th), s in cd_results.items() 
                if s['cagr'] - bench_s['cagr'] > 2.5)
total = len(cd_results)
print()
print(f'  벤치 대비 +2.5%p 초과 조합: {good_count}/{total} ({good_count/total*100:.0f}%)')

# 원본 (60, 0.80) 의 순위
base_diff = cd_results[(60, 0.80)]['cagr'] - bench_s['cagr']
rank = sum(1 for _, s in cd_results.items() 
          if s['cagr'] - bench_s['cagr'] > base_diff) + 1
print(f'  원본 (cd=60, th=0.80) 순위: {rank}/{total}위')

w1_ok = good_count >= 20 and rank <= 10
print(f'  ⚠1 기각 여부: {"✅ 기각 (인근 조합 대부분 양호)" if w1_ok else "⚠ 부분 의혹"}')


# =============================================================================
# ⚠2 리밸런싱 주기 의존 — 주/월/분기
# =============================================================================
print()
print('=' * 100)
print('[⚠2] 리밸런싱 주기 의존')
print('=' * 100)
print(f'{"주기":<12} {"N":>6} {"H3+S2 CAGR":>12} {"벤치 CAGR":>11} {"차이":>9} {"MDD":>9} {"Sharpe":>9}')
print('-' * 100)

ppy_map = {'weekly': 50, 'monthly': 12, 'quarterly': 4}
freq_ok = 0
for freq in ['weekly', 'monthly', 'quarterly']:
    pts, hd_f = get_rebal_pts(freq)
    r, _, _ = run_h3_s2(pts, hd_f, 60, 0.80)
    b = run_bench(pts, hd_f)
    s = stats(r, ppy_map[freq])
    bs = stats(b, ppy_map[freq])
    diff = s['cagr'] - bs['cagr']
    ok = '✅' if diff > 0.5 else ('⚠' if diff > 0 else '❌')
    print(f'{freq:<12} {len(pts):>6} {s["cagr"]:>+11.2f}% {bs["cagr"]:>+10.2f}% '
          f'{diff:>+8.2f}%p {s["mdd"]:>+8.2f}% {s["sharpe"]:>9.3f} {ok}')
    if diff > 0.5: freq_ok += 1

w2_ok = freq_ok >= 2
print()
print(f'  ⚠2 기각 여부: {"✅ 기각" if w2_ok else "⚠ 부분"} ({freq_ok}/3 주기 유효 우위)')


# =============================================================================
# ⚠3 시기 편향 — P1/P2/P3 개별 S2 효과
# =============================================================================
print()
print('=' * 100)
print('[⚠3] 시기 편향 검증 — 각 기간 S2 효과')
print('=' * 100)

h3_orig_rets, _, _ = run_h3_s2(month_pts, hd, 60, 999)  # 999 = 필터 off

print(f'{"기간":<12} {"벤치 CAGR":>11} {"원H3 CAGR":>11} {"S2 CAGR":>11} '
      f'{"원H3-벤치":>11} {"S2-벤치":>11} {"S2 개선":>10}')
print('-' * 100)

period_ok = 0
for p, (start, end) in PERIODS.items():
    mask = np.array([start <= d <= end for d in base_dates])
    if mask.sum() == 0: continue
    h3o = stats(h3_orig_rets[mask])
    s2 = stats(base_rets[mask])
    b = stats(base_bench[mask])
    h3o_diff = h3o['cagr'] - b['cagr']
    s2_diff = s2['cagr'] - b['cagr']
    improvement = s2_diff - h3o_diff
    tag = '✅' if improvement > 0.5 else ('⚠' if improvement > 0 else '❌')
    print(f'{p:<12} {b["cagr"]:>+10.2f}% {h3o["cagr"]:>+10.2f}% {s2["cagr"]:>+10.2f}% '
          f'{h3o_diff:>+10.2f}%p {s2_diff:>+10.2f}%p {improvement:>+9.2f}%p {tag}')
    if improvement > 0: period_ok += 1

w3_ok = period_ok >= 2
print()
print(f'  ⚠3 기각 여부: {"✅ 기각" if w3_ok else "⚠ 부분"} ({period_ok}/3 기간 개선)')


# =============================================================================
# ⚠4 극단치 의존 — 상/하위 제거 시
# =============================================================================
print()
print('=' * 100)
print('[⚠4] 극단치 의존 — 상/하위 N건 제거')
print('=' * 100)

base_diff_full = base_s['cagr'] - bench_s['cagr']
print(f'  원본 차이: {base_diff_full:+.2f}%p (N={len(base_rets)})')
print()

extreme_ok = 0
for n_ex in [3, 5, 10]:
    srt_idx = np.argsort(base_rets)
    keep_idx = srt_idx[n_ex:-n_ex]
    r_ex = base_rets[keep_idx]
    b_ex = base_bench[keep_idx]
    r_s = stats(r_ex)
    b_s_ex = stats(b_ex)
    diff = r_s['cagr'] - b_s_ex['cagr']
    retain = diff / base_diff_full * 100 if base_diff_full != 0 else 0
    tag = '✅' if diff > 1.0 else ('⚠' if diff > 0 else '❌')
    print(f'  상/하위 {n_ex}건씩 제거 (N={len(r_ex)}): '
          f'H3+S2 {r_s["cagr"]:+.2f}% vs 벤치 {b_s_ex["cagr"]:+.2f}% '
          f'(차이 {diff:+.2f}%p, {retain:.0f}% 유지) {tag}')
    if diff > 1.0: extreme_ok += 1

w4_ok = extreme_ok >= 2
print()
print(f'  ⚠4 기각 여부: {"✅ 기각" if w4_ok else "⚠ 부분"}')


# =============================================================================
# ⚠5 우연의 피크 — 인근 조합 표준편차
# =============================================================================
print()
print('=' * 100)
print('[⚠5] 우연의 피크 — 인근 조합 성과 분포')
print('=' * 100)

cagrs = [s['cagr'] for s in cd_results.values()]
mean_cagr = np.mean(cagrs)
std_cagr = np.std(cagrs)
max_cagr = max(cagrs)
min_cagr = min(cagrs)
base_cagr = cd_results[(60, 0.80)]['cagr']

z = (base_cagr - mean_cagr) / std_cagr if std_cagr > 0 else 0

print(f'  5x5 = 25 조합의 CAGR 분포:')
print(f'    평균: {mean_cagr:.2f}%, std: {std_cagr:.2f}%')
print(f'    최대: {max_cagr:.2f}%, 최소: {min_cagr:.2f}%')
print(f'    원본 (60, 0.80): {base_cagr:.2f}% (z={z:+.2f})')
print(f'    변동 폭: {max_cagr - min_cagr:.2f}%p')

w5_ok = (std_cagr < 0.6) and (abs(z) < 2) and (max_cagr - min_cagr < 2.5)
print()
print(f'  ⚠5 기각 여부: {"✅ 기각 (인근 조합 성과 비슷)" if w5_ok else "⚠ 부분 의혹"}')


# =============================================================================
# 최종 판정
# =============================================================================
print()
print('=' * 100)
print('최종 판정 — H3+S2 (cd=60, th=0.80) 5의혹 견고성')
print('=' * 100)
print(f'  ⚠1 파라미터 과적합: {"✅ 기각" if w1_ok else "⚠ 부분"}')
print(f'  ⚠2 리밸런싱 주기:  {"✅ 기각" if w2_ok else "⚠ 부분"}')
print(f'  ⚠3 시기 편향:      {"✅ 기각" if w3_ok else "⚠ 부분"}')
print(f'  ⚠4 극단치 의존:    {"✅ 기각" if w4_ok else "⚠ 부분"}')
print(f'  ⚠5 우연의 피크:    {"✅ 기각" if w5_ok else "⚠ 부분"}')

total_ok = sum([w1_ok, w2_ok, w3_ok, w4_ok, w5_ok])
print()
print(f'  종합: {total_ok}/5 완전 기각')

if total_ok >= 4:
    print('  ✅ H3+S2 실전 적용 가치 확인 (견고성 충분)')
elif total_ok >= 3:
    print('  ⚠ 부분 견고성 — 축소 운영 적합')
else:
    print('  ❌ 견고성 부족 — 추가 검토 필요')

print()
print('완료.')
