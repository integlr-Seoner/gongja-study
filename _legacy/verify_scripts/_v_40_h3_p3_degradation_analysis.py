"""_v_40_h3_p3_degradation_analysis.py — H3 P3 효과 약화 원인 분석

배경:
  _v_38/39 에서 H3 SPREAD 의 P3 (2023~2026) 효과가 +0.24%p 로 급감.
  P1 +5.27%p / P2 +2.51%p / P3 +0.24%p → 실전 적용 전 원인 진단 필수.

가설 4개:
  G1 벤치 자체 강세 — P3 은 벤치도 강해서 상대 우위 어려움
  G2 스프레드 빈도 변화 — P3 에 |spread|>3%p 발생 빈도 변화
  G3 지수 상관관계 증가 — KOSPI/KOSDAQ 동조화로 로테이션 가치 소실
  G4 이벤트 노이즈 — P1/P2 의 특정 이벤트가 결과를 과대 포장

판정:
  G1/G2 확인 → "일시적" → H3 유지 (단 기대치 조정)
  G3 확인 → "구조적" → H3 효과 영속적 약화 → 포기 또는 수정
  G4 확인 → P1/P2 의 강한 결과 자체가 우연 → H3 자체 재평가
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
dates = np.array(common_dates)
n = len(common_dates)

PERIODS = {
    'P1 (14~18)': ('20140101', '20181231'),
    'P2 (19~22)': ('20190101', '20221231'),
    'P3 (23~26)': ('20230101', '20261231'),
}


# 월별 리밸런싱 시점
month_pts = []
cy = ''
for i, d in enumerate(common_dates):
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        month_pts.append(i); cy = ym
month_pts = [p for p in month_pts if p + 20 < n and p >= 20]

# 각 시점별 데이터 축적
pts_data = []
for i in month_pts:
    date_str = common_dates[i]
    ret_k_20d = (kospi_c[i] / kospi_c[i-20] - 1) * 100
    ret_q_20d = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
    spread = ret_k_20d - ret_q_20d
    
    if spread > 3: choice = 'KOSDAQ'
    elif spread < -3: choice = 'KOSPI'
    else: choice = 'EQUAL'
    
    # 보유 20일 수익
    r_k = kospi_c[i+20] / kospi_c[i] - 1
    r_q = kosdaq_c[i+20] / kosdaq_c[i] - 1
    if choice == 'KOSPI': ret_h3 = r_k
    elif choice == 'KOSDAQ': ret_h3 = r_q
    else: ret_h3 = (r_k + r_q) / 2
    ret_bench = (r_k + r_q) / 2
    
    period = None
    for p, (s, e) in PERIODS.items():
        if s <= date_str <= e:
            period = p; break
    
    pts_data.append({
        'date': date_str, 'period': period,
        'spread_20d': spread, 'choice': choice,
        'ret_h3': ret_h3, 'ret_bench': ret_bench,
        'ret_kospi': r_k, 'ret_kosdaq': r_q,
        'i': i,
    })


# =============================================================================
# G1 벤치 자체 강세 검증
# =============================================================================
print('=' * 100)
print('[G1] 벤치 자체 강세 검증')
print('=' * 100)
print(f'{"기간":<12} {"N":>5} {"벤치 평균":>11} {"벤치 std":>11} {"벤치 승률":>10} {"양수 비율":>10}')
print('-' * 100)

g1_data = {}
for p in PERIODS:
    sub = [x for x in pts_data if x['period'] == p]
    if not sub: continue
    bench_rets = np.array([x['ret_bench'] for x in sub]) * 100
    g1_data[p] = {
        'mean': bench_rets.mean(), 'std': bench_rets.std(),
        'win': (bench_rets > 0).mean() * 100,
        'n': len(sub),
    }
    print(f'{p:<12} {len(sub):>5} {bench_rets.mean():>+10.3f}% {bench_rets.std():>10.3f}% '
          f'{(bench_rets>0).mean()*100:>9.1f}% {(bench_rets>0).sum():>5}/{len(sub):<5}')

# G1 판정: P3 벤치 강세가 P1/P2 보다 명확히 높으면 G1 확인
if 'P3 (23~26)' in g1_data and 'P1 (14~18)' in g1_data:
    p3_bench = g1_data['P3 (23~26)']['mean']
    p1_bench = g1_data['P1 (14~18)']['mean']
    print(f'\n  P3 벤치 평균 {p3_bench:+.3f}% vs P1 벤치 평균 {p1_bench:+.3f}%')
    if p3_bench > p1_bench + 0.5:
        print(f'  ✅ G1 확인: P3 벤치가 {p3_bench - p1_bench:+.2f}%p 강함 → 상대우위 얻기 어려움')
        g1_verdict = True
    else:
        print(f'  ❌ G1 기각: P3 벤치 강세 명확히 크지 않음')
        g1_verdict = False


# =============================================================================
# G2 스프레드 빈도 변화 검증
# =============================================================================
print()
print('=' * 100)
print('[G2] 스프레드 빈도 변화 검증')
print('=' * 100)
print(f'{"기간":<12} {"N":>5} {"KOSPI 선택":>11} {"KOSDAQ 선택":>12} {"EQUAL":>8} '
      f'{"|spread|avg":>13} {"|spread|max":>13}')
print('-' * 100)

g2_data = {}
for p in PERIODS:
    sub = [x for x in pts_data if x['period'] == p]
    if not sub: continue
    c = Counter(x['choice'] for x in sub)
    abs_spreads = [abs(x['spread_20d']) for x in sub]
    g2_data[p] = {
        'kospi_pct': c.get('KOSPI', 0) / len(sub) * 100,
        'kosdaq_pct': c.get('KOSDAQ', 0) / len(sub) * 100,
        'equal_pct': c.get('EQUAL', 0) / len(sub) * 100,
        'abs_avg': np.mean(abs_spreads),
        'abs_max': max(abs_spreads),
        'n': len(sub),
    }
    print(f'{p:<12} {len(sub):>5} '
          f'{c.get("KOSPI", 0):>4} ({c.get("KOSPI", 0)/len(sub)*100:>5.1f}%) '
          f'{c.get("KOSDAQ", 0):>4} ({c.get("KOSDAQ", 0)/len(sub)*100:>5.1f}%) '
          f'{c.get("EQUAL", 0):>3} ({c.get("EQUAL", 0)/len(sub)*100:>4.1f}%) '
          f'{np.mean(abs_spreads):>12.2f}%p {max(abs_spreads):>12.2f}%p')

# G2 판정: P3 에서 EQUAL 비중이 현저히 높거나, |spread| 평균이 작으면 확인
if 'P3 (23~26)' in g2_data and 'P1 (14~18)' in g2_data:
    p3_equal = g2_data['P3 (23~26)']['equal_pct']
    p1_equal = g2_data['P1 (14~18)']['equal_pct']
    p3_abs = g2_data['P3 (23~26)']['abs_avg']
    p1_abs = g2_data['P1 (14~18)']['abs_avg']
    print(f'\n  P3 EQUAL 비중 {p3_equal:.1f}% vs P1 EQUAL 비중 {p1_equal:.1f}%')
    print(f'  P3 |spread| 평균 {p3_abs:.2f}%p vs P1 {p1_abs:.2f}%p')
    # EQUAL 비중 더 높거나 스프레드 평균 작으면 "신호 부족"
    if p3_equal > p1_equal + 5 or p3_abs < p1_abs - 0.5:
        print(f'  ✅ G2 확인: P3 에 신호 발생 빈도/크기 감소 → 로테이션 기회 감소')
        g2_verdict = True
    else:
        print(f'  ❌ G2 기각: 신호 발생 빈도 P1 과 유사')
        g2_verdict = False


# =============================================================================
# G3 KOSPI/KOSDAQ 상관관계 변화
# =============================================================================
print()
print('=' * 100)
print('[G3] KOSPI/KOSDAQ 상관관계 변화 검증')
print('=' * 100)
print(f'{"기간":<12} {"N":>5} {"상관계수 (20d)":>16} {"벤치vs선택 차이":>18}')
print('-' * 100)

g3_data = {}
for p in PERIODS:
    sub = [x for x in pts_data if x['period'] == p]
    if not sub: continue
    kospi_rets = np.array([x['ret_kospi'] for x in sub]) * 100
    kosdaq_rets = np.array([x['ret_kosdaq'] for x in sub]) * 100
    corr = np.corrcoef(kospi_rets, kosdaq_rets)[0, 1]
    # H3 선택 vs 벤치 평균 차이 (로테이션 기여도)
    h3_rets = np.array([x['ret_h3'] for x in sub]) * 100
    bench_rets = np.array([x['ret_bench'] for x in sub]) * 100
    diff_mean = (h3_rets - bench_rets).mean()
    g3_data[p] = {'corr': corr, 'diff': diff_mean, 'n': len(sub)}
    print(f'{p:<12} {len(sub):>5} {corr:>15.4f} {diff_mean:>+17.3f}%')

# G3 판정: P3 상관계수가 1에 가까우면 (e.g. > 0.85) 로테이션 가치 소실
if 'P3 (23~26)' in g3_data:
    p3_corr = g3_data['P3 (23~26)']['corr']
    p1_corr = g3_data['P1 (14~18)']['corr']
    print(f'\n  P1 → P3 상관계수 변화: {p1_corr:.3f} → {p3_corr:.3f}')
    if p3_corr > p1_corr + 0.10 or p3_corr > 0.85:
        print(f'  ✅ G3 확인: P3 에 KOSPI/KOSDAQ 동조화 강해짐 → 로테이션 가치 감소')
        g3_verdict = True
    else:
        print(f'  ❌ G3 기각: 상관관계 변화 크지 않음')
        g3_verdict = False


# =============================================================================
# G4 이벤트 노이즈 (P1/P2 특정 시점 제거 시 효과 변화)
# =============================================================================
print()
print('=' * 100)
print('[G4] 이벤트 노이즈 검증 — P1/P2 의 극단 월 제거 시')
print('=' * 100)

# P1/P2 전체에서 H3-벤치 차이 상위/하위 3건 식별
p1p2_pts = [x for x in pts_data if x['period'] in ('P1 (14~18)', 'P2 (19~22)')]
for x in p1p2_pts:
    x['excess'] = x['ret_h3'] - x['ret_bench']

# 상위 3건 (H3 가 벤치 크게 초과한 달)
top3 = sorted(p1p2_pts, key=lambda x: -x['excess'])[:3]
bot3 = sorted(p1p2_pts, key=lambda x: x['excess'])[:3]

print(f'\n  P1/P2 에서 H3 초과수익 상위 3건:')
for x in top3:
    print(f'    {x["date"]} [{x["period"]}] spread={x["spread_20d"]:+.2f}%p '
          f'choice={x["choice"]} H3={x["ret_h3"]*100:+.2f}% bench={x["ret_bench"]*100:+.2f}% '
          f'(초과 {x["excess"]*100:+.3f}%p)')

print(f'\n  P1/P2 에서 H3 초과수익 하위 3건:')
for x in bot3:
    print(f'    {x["date"]} [{x["period"]}] spread={x["spread_20d"]:+.2f}%p '
          f'choice={x["choice"]} H3={x["ret_h3"]*100:+.2f}% bench={x["ret_bench"]*100:+.2f}% '
          f'(초과 {x["excess"]*100:+.3f}%p)')

# 극단 월 제거 시 P1/P2 차이 축소 여부
to_remove = set((x['date'] for x in top3))
p1p2_filtered = [x for x in p1p2_pts if x['date'] not in to_remove]
h3_f = np.array([x['ret_h3'] for x in p1p2_filtered])
b_f = np.array([x['ret_bench'] for x in p1p2_filtered])
diff_full = np.mean([x['excess'] for x in p1p2_pts]) * 100
diff_filtered = (h3_f - b_f).mean() * 100
print(f'\n  P1/P2 원본 초과수익 평균: {diff_full:+.3f}%p')
print(f'  상위 3건 제거 후 초과수익 평균: {diff_filtered:+.3f}%p '
      f'(변화 {diff_filtered-diff_full:+.3f}%p)')

# G4 판정: 상위 3건 제거 시 초과수익이 절반 이하로 떨어지면 G4 확인
if diff_full > 0 and diff_filtered / diff_full < 0.5:
    print(f'  ✅ G4 확인: 상위 3건이 P1/P2 우위를 과대 포장')
    g4_verdict = True
else:
    print(f'  ❌ G4 기각: 극단 월 제거해도 우위 유지')
    g4_verdict = False


# =============================================================================
# 종합 판정 + 실전 적용 권고
# =============================================================================
print()
print('=' * 100)
print('종합 판정')
print('=' * 100)
print(f'  G1 벤치 자체 강세:    {"✅ 확인" if g1_verdict else "❌ 기각"}')
print(f'  G2 스프레드 빈도 변화: {"✅ 확인" if g2_verdict else "❌ 기각"}')
print(f'  G3 상관관계 증가:     {"✅ 확인" if g3_verdict else "❌ 기각"}')
print(f'  G4 이벤트 노이즈:     {"✅ 확인" if g4_verdict else "❌ 기각"}')

print()
print('=' * 100)
print('실전 적용 권고')
print('=' * 100)
confirmed = sum([g1_verdict, g2_verdict, g3_verdict, g4_verdict])
if g3_verdict or g4_verdict:
    print('  ⚠ 구조적 약화 감지 — H3 실전 적용 신중히 재검토')
    if g3_verdict:
        print('    → KOSPI/KOSDAQ 동조화 → 로테이션 효과 영속적 감소 가능성')
    if g4_verdict:
        print('    → P1/P2 우위가 특정 이벤트로 과대 포장됨')
elif g1_verdict and not g2_verdict:
    print('  ✅ 일시적 약화 — H3 유지 가능 (단 벤치 강세기에 상대우위 축소 인정)')
    print('    → 포지션 축소 20% 타당, 절대수익 여전히 양수')
elif g2_verdict:
    print('  ⚠ 신호 발생 빈도 감소 — H3 임계값 완화 검토 (±2%p 등)')

print()
print('완료.')
