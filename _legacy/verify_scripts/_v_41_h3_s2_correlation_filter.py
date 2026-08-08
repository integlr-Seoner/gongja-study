"""_v_41_h3_s2_correlation_filter.py — H3 SPREAD + S2 상관계수 필터 검증

배경:
  _v_40 에서 H3 P3 약화 원인 = G3 KOSPI/KOSDAQ 상관관계 증가 확인.
  S2 해결책: 상관계수 > threshold 이면 EQUAL 강제 (로테이션 차단).

가설:
  동조화 강한 시기에는 어느 쪽 선택해도 비슷 → EQUAL 이 안전
  상관계수 임계값 0.75 전후가 G3 결과상 논리적 정답

검증:
  임계값 6개 (0.60/0.70/0.75/0.80/0.85/0.90) × 상관계수 기간 3개 (20d/40d/60d)
  각 조합의 13년 CAGR + P3 개선 여부
  필터 활성화 빈도 (얼마나 자주 EQUAL 강제?)
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

# 월별 리밸런싱 시점
month_pts = []
cy = ''
for i, d in enumerate(common_dates):
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        month_pts.append(i); cy = ym

# 상관계수 계산 위해 최대 60일 필요
month_pts = [p for p in month_pts if p + 20 < n and p >= 60]
print(f'리밸런싱 시점: {len(month_pts)}회')

PERIODS = {
    'P1 (14~18)': ('20140101', '20181231'),
    'P2 (19~22)': ('20190101', '20221231'),
    'P3 (23~26)': ('20230101', '20261231'),
}


def rolling_correlation(i, days):
    """시점 i 에서 직전 days 영업일의 KOSPI vs KOSDAQ 일일 수익률 상관계수"""
    if i < days: return None
    # 직전 days 일간 일일 수익률 (close 대비)
    kospi_slice = kospi_c[i-days:i+1]
    kosdaq_slice = kosdaq_c[i-days:i+1]
    k_rets = np.diff(kospi_slice) / kospi_slice[:-1]
    q_rets = np.diff(kosdaq_slice) / kosdaq_slice[:-1]
    if len(k_rets) < 2 or k_rets.std() == 0 or q_rets.std() == 0:
        return None
    return float(np.corrcoef(k_rets, q_rets)[0, 1])


def run_h3_s2(corr_days, corr_threshold, spread_threshold=3.0, holding=20):
    """H3 + S2 상관계수 필터
    
    상관계수 > corr_threshold: EQUAL 강제
    그 외: spread 기반 H3 원본 로직
    """
    rets = []; choices = []; pt_dates = []; filtered_count = 0
    for i in month_pts:
        # 상관계수
        corr = rolling_correlation(i, corr_days)
        
        # 스프레드
        ret_k = (kospi_c[i] / kospi_c[i-20] - 1) * 100
        ret_q = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
        spread = ret_k - ret_q
        
        # 선택 결정
        if corr is not None and corr > corr_threshold:
            choice = 'EQUAL'  # 필터 발동
            filtered_count += 1
        else:
            # H3 원본
            if spread > spread_threshold: choice = 'KOSDAQ'
            elif spread < -spread_threshold: choice = 'KOSPI'
            else: choice = 'EQUAL'
        
        # 보유 수익률
        r_k = kospi_c[i+holding] / kospi_c[i] - 1
        r_q = kosdaq_c[i+holding] / kosdaq_c[i] - 1
        if choice == 'KOSPI': r = r_k
        elif choice == 'KOSDAQ': r = r_q
        else: r = (r_k + r_q) / 2
        
        rets.append(r); choices.append(choice); pt_dates.append(common_dates[i])
    return np.array(rets), choices, pt_dates, filtered_count


def run_bench(holding=20):
    rets = []
    for i in month_pts:
        r_k = kospi_c[i+holding] / kospi_c[i] - 1
        r_q = kosdaq_c[i+holding] / kosdaq_c[i] - 1
        rets.append((r_k + r_q) / 2)
    return np.array(rets)


def stats(rets, periods_per_year=12):
    if len(rets) == 0:
        return {'cum': 0, 'cagr': 0, 'mdd': 0, 'sharpe': 0, 'win': 0, 'n': 0, 'mean': 0, 'std': 0}
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
    return {'cum': cum*100, 'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe,
            'win': win, 'mean': mean, 'std': std, 'n': len(rets)}


def period_stats(rets, pt_dates):
    """각 기간별 쪼개서 stats"""
    result = {}
    for p, (start, end) in PERIODS.items():
        mask = [start <= d <= end for d in pt_dates]
        sub = rets[mask]
        result[p] = stats(sub)
    return result


# =============================================================================
# [1/4] 기준선: H3 원본 + 벤치마크
# =============================================================================
print()
print('=' * 100)
print('[1/4] 기준선')
print('=' * 100)

h3_orig, h3_ch, h3_dates, _ = run_h3_s2(
    corr_days=20, corr_threshold=999, spread_threshold=3.0)  # 필터 비활성
bench = run_bench()

bench_s = stats(bench)
h3_s = stats(h3_orig)
print(f'  벤치마크 (EQUAL):  CAGR {bench_s["cagr"]:+.2f}%, MDD {bench_s["mdd"]:+.2f}%, '
      f'Sharpe {bench_s["sharpe"]:.3f}')
print(f'  H3 원본 (필터 X):  CAGR {h3_s["cagr"]:+.2f}%, MDD {h3_s["mdd"]:+.2f}%, '
      f'Sharpe {h3_s["sharpe"]:.3f}')
print(f'  원본 차이: {h3_s["cagr"] - bench_s["cagr"]:+.2f}%p')

# 기간별 원본 성과
h3_periods = period_stats(h3_orig, h3_dates)
bench_periods = period_stats(bench, h3_dates)
print()
print(f'  {"기간":<12} {"H3 CAGR":>10} {"벤치 CAGR":>11} {"차이":>10}')
for p in PERIODS:
    diff = h3_periods[p]['cagr'] - bench_periods[p]['cagr']
    print(f'  {p:<12} {h3_periods[p]["cagr"]:>+9.2f}% {bench_periods[p]["cagr"]:>+10.2f}% {diff:>+9.2f}%p')


# =============================================================================
# [2/4] 상관계수 임계값 × 계산기간 그리드 탐색
# =============================================================================
print()
print('=' * 100)
print('[2/4] S2 필터: 상관계수 임계값 × 계산기간 그리드')
print('=' * 100)

GRID = {
    'thresholds': [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 999],  # 999 = 필터 off (원본)
    'corr_days': [20, 40, 60],
}

print(f'{"corr_days":<12} {"threshold":<10} {"N필터":>6} {"필터%":>7} '
      f'{"CAGR":>9} {"vs벤치":>8} {"MDD":>9} {"Sharpe":>9}')
print('-' * 100)

results = {}
for corr_days in GRID['corr_days']:
    for th in GRID['thresholds']:
        r, ch, dts, n_filter = run_h3_s2(corr_days, th)
        s = stats(r)
        pct = n_filter / len(r) * 100
        diff = s['cagr'] - bench_s['cagr']
        results[(corr_days, th)] = {
            'cagr': s['cagr'], 'mdd': s['mdd'], 'sharpe': s['sharpe'],
            'diff': diff, 'n_filter': n_filter, 'pct': pct,
            'rets': r, 'dates': dts,
        }
        tag = ' ⭐' if diff > 3.5 else ''
        print(f'{corr_days:<12} '
              f'{"off" if th == 999 else f"{th:.2f}":<10} '
              f'{n_filter:>6} {pct:>6.1f}% '
              f'{s["cagr"]:>+8.2f}% {diff:>+7.2f}%p {s["mdd"]:>+8.2f}% '
              f'{s["sharpe"]:>9.3f}{tag}')
    print('-' * 100)


# =============================================================================
# [3/4] 최상위 조합의 3기간 분해 — P3 개선 여부 확인
# =============================================================================
print()
print('=' * 100)
print('[3/4] 최상위 조합의 P1/P2/P3 분해')
print('=' * 100)

# diff 큰 순 상위 5개 추출 (필터 off 제외)
top5 = sorted(
    [(k, v) for k, v in results.items() if k[1] != 999],
    key=lambda x: -x[1]['diff']
)[:5]

print(f'{"조합":<20} {"CAGR":>9} {"vs벤치":>8} {"P1 차이":>10} {"P2 차이":>10} {"P3 차이":>10} {"MDD":>9}')
print('-' * 100)

for (cd, th), v in top5:
    p = period_stats(v['rets'], v['dates'])
    b = period_stats(bench, h3_dates)  # 벤치는 고정
    p1_diff = p['P1 (14~18)']['cagr'] - b['P1 (14~18)']['cagr']
    p2_diff = p['P2 (19~22)']['cagr'] - b['P2 (19~22)']['cagr']
    p3_diff = p['P3 (23~26)']['cagr'] - b['P3 (23~26)']['cagr']
    print(f'cd={cd},th={th:.2f}        '
          f'{v["cagr"]:>+8.2f}% {v["diff"]:>+7.2f}%p '
          f'{p1_diff:>+9.2f}%p {p2_diff:>+9.2f}%p {p3_diff:>+9.2f}%p {v["mdd"]:>+8.2f}%')

# 원본 H3 와 비교
print()
print(f'  원본 H3 (필터 off): P1 +5.27%p / P2 +2.51%p / P3 +0.24%p')
print(f'  → S2 필터가 P3 개선했는지 위에서 확인')


# =============================================================================
# [4/4] 권고 조합 상세 분석
# =============================================================================
print()
print('=' * 100)
print('[4/4] 권고 조합 상세')
print('=' * 100)

if top5:
    best = top5[0]
    (cd, th) = best[0]
    v = best[1]
    r, ch, dts, n_filter = run_h3_s2(cd, th)
    
    print(f'\n★ 최강 조합: corr_days={cd}, threshold={th:.2f}')
    print(f'  CAGR: {v["cagr"]:+.2f}% (원본 H3 {h3_s["cagr"]:+.2f}% 대비 {v["cagr"]-h3_s["cagr"]:+.2f}%p)')
    print(f'  MDD:  {v["mdd"]:+.2f}% (원본 {h3_s["mdd"]:+.2f}% 대비 {v["mdd"]-h3_s["mdd"]:+.2f}%p)')
    print(f'  Sharpe: {v["sharpe"]:.3f} (원본 {h3_s["sharpe"]:.3f} 대비 {v["sharpe"]-h3_s["sharpe"]:+.3f})')
    print(f'  필터 발동: {v["n_filter"]}회 ({v["pct"]:.1f}%)')
    
    # 선택 분포
    c = Counter(ch)
    print(f'\n  선택 분포: KOSPI {c.get("KOSPI",0)}회 ({c.get("KOSPI",0)/len(ch)*100:.1f}%) / '
          f'KOSDAQ {c.get("KOSDAQ",0)}회 ({c.get("KOSDAQ",0)/len(ch)*100:.1f}%) / '
          f'EQUAL {c.get("EQUAL",0)}회 ({c.get("EQUAL",0)/len(ch)*100:.1f}%)')
    
    # 기간별 상세
    p = period_stats(r, dts)
    b = period_stats(bench, h3_dates)
    print(f'\n  {"기간":<12} {"S2+H3 CAGR":>12} {"벤치 CAGR":>11} {"차이":>10}')
    for pname in PERIODS:
        diff = p[pname]['cagr'] - b[pname]['cagr']
        print(f'  {pname:<12} {p[pname]["cagr"]:>+11.2f}% {b[pname]["cagr"]:>+10.2f}% {diff:>+9.2f}%p')


# =============================================================================
# 판정 + 권고
# =============================================================================
print()
print('=' * 100)
print('판정')
print('=' * 100)

# P3 개선 확인
if top5:
    (cd, th) = top5[0][0]
    r, _, dts, _ = run_h3_s2(cd, th)
    p3_rets = r[[PERIODS['P3 (23~26)'][0] <= d <= PERIODS['P3 (23~26)'][1] for d in dts]]
    bench_p3 = bench[[PERIODS['P3 (23~26)'][0] <= d <= PERIODS['P3 (23~26)'][1] for d in h3_dates]]
    s2_p3 = stats(p3_rets)
    bench_p3_s = stats(bench_p3)
    p3_diff = s2_p3['cagr'] - bench_p3_s['cagr']
    orig_p3_diff = 0.24  # _v_39 원본 H3 결과
    
    print(f'  원본 H3의 P3 차이: +{orig_p3_diff:.2f}%p')
    print(f'  S2+H3의 P3 차이:   {p3_diff:+.2f}%p')
    
    if p3_diff > orig_p3_diff + 1.0:
        verdict = '✅ S2 필터가 P3 개선 — 실전 적용 가치 확인'
    elif p3_diff > orig_p3_diff:
        verdict = '⚠ S2 필터 약간 개선 — 적용 여부 한계적'
    else:
        verdict = '❌ S2 필터 효과 없음 — G3 진단 불일치 또는 구조적 한계 심함'
    print(f'\n  결론: {verdict}')

print()
print('완료.')
