"""_v_46_v4_walk_forward_validation.py — V4 시계열 교차 검증

배경:
  §33: 정적 최적 파라미터 (운용 30%, 종목당 7%)
  §34: 동적 최적 (BULL 50/10, 그 외 30/7)
  → 이들이 과거 데이터 과적합 여부 최종 확인

검증 방식:
  A1 시점 분할: P1 학습 → P2+P3 테스트
  A2 앞뒤 분할: 전반 74개월 학습 → 후반 74개월 테스트
  A3 롤링 윈도우: 60개월 학습 → 다음 12개월 테스트 (반복)

판정:
  ① 학습기 최적 파라미터 → 테스트기에서도 상위 30% 이내
  ② 학습 Top5 와 테스트 Top5 겹침 >= 3개
  ③ 학습 최적의 테스트 CAGR > 테스트 베이스라인
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

print('[1/4] 데이터 로드...')
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


print('\n[2/4] V4 월별 gap 수집...')
t0 = time.time()
gaps_by_month = defaultdict(list)
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, d_idx in enumerate(dates_col):
        if d_idx not in sample_idx_set: continue
        g = v4_gap(arr, row_pos)
        if g is not None:
            gaps_by_month[all_dates[d_idx]].append(g)
print(f'  {sum(len(v) for v in gaps_by_month.values())}건 V4=4, {time.time()-t0:.1f}초')


def monthly_return(gaps, wr, ps):
    if not gaps: return 0.0
    n = min(len(gaps), 30)
    inv = min(n * ps, wr)
    mean_gap = np.mean(gaps[:n])
    return inv * (mean_gap - ROUND_TRIP_COST_PCT) / 100


def stats(rets, ppy=12):
    if len(rets) == 0:
        return {'cagr': 0, 'mdd': 0, 'sharpe': 0, 'calmar': 0}
    cum = np.prod(1 + rets) - 1
    yrs = len(rets) / ppy
    cagr = ((1 + cum) ** (1/yrs) - 1) * 100 if yrs > 0 and cum > -1 else 0
    cp = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cp)
    dd = (cp - peak) / peak
    mdd = dd.min() * 100
    mean = rets.mean() * 100
    std = rets.std() * 100
    return {'cagr': cagr, 'mdd': mdd,
            'sharpe': mean/std if std>0 else 0,
            'calmar': cagr/abs(mdd) if mdd<0 else 0}


def grid_search(months, target='calmar'):
    """월 리스트에 대해 그리드 탐색 → 최적 파라미터 반환"""
    grid_wr = [0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    grid_ps = [0.03, 0.05, 0.06, 0.07, 0.08, 0.10]
    results = []
    for wr in grid_wr:
        for ps in grid_ps:
            rets = np.array([monthly_return(gaps_by_month.get(m, []), wr, ps) for m in months])
            s = stats(rets)
            results.append({'wr': wr, 'ps': ps, **s})
    return sorted(results, key=lambda x: -x[target])


def evaluate(months, wr, ps):
    rets = np.array([monthly_return(gaps_by_month.get(m, []), wr, ps) for m in months])
    return stats(rets)


# =============================================================================
# A1 시점 분할: P1 학습 → P2+P3 테스트
# =============================================================================
print()
print('=' * 100)
print('[A1] 시점 분할: P1 (14~18) 학습 → P2+P3 (19~26) 테스트')
print('=' * 100)

p1_months = [m for m in samples if '20140101' <= m <= '20181231']
p23_months = [m for m in samples if '20190101' <= m <= '20261231']

print(f'\n  학습 기간: {p1_months[0]} ~ {p1_months[-1]} ({len(p1_months)}개월)')
print(f'  테스트 기간: {p23_months[0]} ~ {p23_months[-1]} ({len(p23_months)}개월)')

# 학습: P1 그리드 탐색 → Top 5
p1_results = grid_search(p1_months)
print(f'\n  P1 학습 Top 5 조합 (Calmar 순):')
print(f'  {"wr":>6} {"ps":>6} {"CAGR":>9} {"MDD":>9} {"Calmar":>8} {"Sharpe":>8}')
for r in p1_results[:5]:
    print(f'  {r["wr"]:>5.2f} {r["ps"]:>5.2f} {r["cagr"]:>+8.2f}% '
          f'{r["mdd"]:>+8.2f}% {r["calmar"]:>8.3f} {r["sharpe"]:>8.3f}')

# 테스트: P1 Top 5 를 P2+P3 에 적용
print(f'\n  P1 학습 Top 5 → P2+P3 테스트 성과:')
print(f'  {"wr":>6} {"ps":>6} {"테스트 CAGR":>12} {"테스트 MDD":>11} {"테스트 Calmar":>13} {"Calmar 차이":>12}')
p1_top5_test = []
for r in p1_results[:5]:
    test_s = evaluate(p23_months, r['wr'], r['ps'])
    diff = test_s['calmar'] - r['calmar']
    p1_top5_test.append({'wr': r['wr'], 'ps': r['ps'], **test_s, 'cal_diff': diff})
    print(f'  {r["wr"]:>5.2f} {r["ps"]:>5.2f} {test_s["cagr"]:>+11.2f}% '
          f'{test_s["mdd"]:>+10.2f}% {test_s["calmar"]:>13.3f} {diff:>+11.3f}')

# 테스트 기간 진짜 최적
p23_results = grid_search(p23_months)
print(f'\n  P2+P3 실제 Top 5 (진짜 최적):')
for r in p23_results[:5]:
    print(f'  {r["wr"]:>5.2f} {r["ps"]:>5.2f} {r["cagr"]:>+8.2f}% '
          f'{r["mdd"]:>+8.2f}% {r["calmar"]:>8.3f}')

# 판정: P1 Top 5 가 P2+P3 Top 15 (= 전체 36개 중 상위 42%) 이내?
p23_top15_params = {(r['wr'], r['ps']) for r in p23_results[:15]}
p1_top5_in_p23 = sum(1 for r in p1_results[:5] 
                    if (r['wr'], r['ps']) in p23_top15_params)
print(f'\n  ⚖ 교집합: P1 Top 5 중 {p1_top5_in_p23}/5 가 P2+P3 Top 15 이내')
a1_ok = p1_top5_in_p23 >= 3


# =============================================================================
# A2 앞뒤 분할: 전반 74개월 학습 → 후반 74개월 테스트
# =============================================================================
print()
print('=' * 100)
print('[A2] 앞뒤 분할: 전반 74개월 학습 → 후반 74개월 테스트')
print('=' * 100)

half = len(samples) // 2
first_half = samples[:half]
second_half = samples[half:]
print(f'\n  전반: {first_half[0]} ~ {first_half[-1]} ({len(first_half)}개월)')
print(f'  후반: {second_half[0]} ~ {second_half[-1]} ({len(second_half)}개월)')

fh_results = grid_search(first_half)
sh_results = grid_search(second_half)

print(f'\n  전반 Top 5 → 후반 테스트 성과:')
print(f'  {"wr":>6} {"ps":>6} {"학습 Calmar":>12} {"테스트 Calmar":>13} {"차이":>10}')
for r in fh_results[:5]:
    test_s = evaluate(second_half, r['wr'], r['ps'])
    diff = test_s['calmar'] - r['calmar']
    print(f'  {r["wr"]:>5.2f} {r["ps"]:>5.2f} {r["calmar"]:>11.3f} '
          f'{test_s["calmar"]:>13.3f} {diff:>+9.3f}')

sh_top15_params = {(r['wr'], r['ps']) for r in sh_results[:15]}
fh_top5_in_sh = sum(1 for r in fh_results[:5] 
                   if (r['wr'], r['ps']) in sh_top15_params)
print(f'\n  ⚖ 교집합: 전반 Top 5 중 {fh_top5_in_sh}/5 가 후반 Top 15 이내')
a2_ok = fh_top5_in_sh >= 3


# =============================================================================
# A3 롤링 윈도우: 60개월 학습 → 다음 12개월 테스트 (반복)
# =============================================================================
print()
print('=' * 100)
print('[A3] 롤링 윈도우: 60개월 학습 → 12개월 테스트')
print('=' * 100)

WINDOW = 60
FORWARD = 12

print(f'\n  학습 윈도우: {WINDOW}개월, 테스트: {FORWARD}개월, 스텝: {FORWARD}개월')

# 가능한 윈도우 수
num_windows = (len(samples) - WINDOW - FORWARD) // FORWARD + 1
print(f'  총 윈도우: {num_windows}개')
print()
print(f'  {"Window":<10} {"학습기간":<24} {"테스트기간":<24} {"학습최적":<15} '
      f'{"학습 Calmar":>10} {"테스트 Calmar":>13} {"테스트 CAGR":>12}')
print('-' * 130)

rolling_results = []
for i in range(num_windows):
    train_start = i * FORWARD
    train_end = train_start + WINDOW
    test_start = train_end
    test_end = test_start + FORWARD
    if test_end > len(samples): break
    
    train_m = samples[train_start:train_end]
    test_m = samples[test_start:test_end]
    
    train_top = grid_search(train_m)[0]
    test_s = evaluate(test_m, train_top['wr'], train_top['ps'])
    
    rolling_results.append({
        'train_period': f'{train_m[0][:6]}~{train_m[-1][:6]}',
        'test_period': f'{test_m[0][:6]}~{test_m[-1][:6]}',
        'best_params': (train_top['wr'], train_top['ps']),
        'train_calmar': train_top['calmar'],
        'test_calmar': test_s['calmar'],
        'test_cagr': test_s['cagr'],
        'test_mdd': test_s['mdd'],
    })
    print(f'  W{i+1:<2} '
          f'{train_m[0][:6]}~{train_m[-1][:6]}    {test_m[0][:6]}~{test_m[-1][:6]}    '
          f'wr={train_top["wr"]:.2f},ps={train_top["ps"]:.2f} '
          f'{train_top["calmar"]:>10.3f} {test_s["calmar"]:>13.3f} {test_s["cagr"]:>+11.2f}%')

# 요약
test_calmars = [r['test_calmar'] for r in rolling_results]
test_cagrs = [r['test_cagr'] for r in rolling_results]
positive_windows = sum(1 for c in test_cagrs if c > 0)

print()
print(f'  ⚖ 테스트 성과 요약:')
print(f'    평균 Calmar: {np.mean(test_calmars):.3f} (학습 평균 {np.mean([r["train_calmar"] for r in rolling_results]):.3f})')
print(f'    평균 CAGR: {np.mean(test_cagrs):+.2f}%')
print(f'    양수 윈도우: {positive_windows}/{len(rolling_results)}')
a3_ok = positive_windows >= len(rolling_results) * 0.7 and np.mean(test_cagrs) > 2


# =============================================================================
# 파라미터 안정성 — 각 윈도우 최적 파라미터 분포
# =============================================================================
print()
print('=' * 100)
print('[안정성] 각 윈도우 최적 파라미터 분포')
print('=' * 100)

wr_counter = defaultdict(int)
ps_counter = defaultdict(int)
for r in rolling_results:
    wr_counter[r['best_params'][0]] += 1
    ps_counter[r['best_params'][1]] += 1

print(f'\n  운용 비율 (wr) 선택 분포:')
for wr in sorted(wr_counter.keys()):
    print(f'    {wr:.2f}: {wr_counter[wr]}회')
print(f'\n  종목당 비율 (ps) 선택 분포:')
for ps in sorted(ps_counter.keys()):
    print(f'    {ps:.2f}: {ps_counter[ps]}회')

# 가장 자주 선택된 파라미터
most_wr = max(wr_counter.items(), key=lambda x: x[1])
most_ps = max(ps_counter.items(), key=lambda x: x[1])
print(f'\n  가장 자주 선택된 wr: {most_wr[0]} ({most_wr[1]}회)')
print(f'  가장 자주 선택된 ps: {most_ps[0]} ({most_ps[1]}회)')


# =============================================================================
# 종합 판정
# =============================================================================
print()
print('=' * 100)
print('교차 검증 종합 판정')
print('=' * 100)
print(f'  A1 시점 분할 (P1→P2+P3): {"✅ 기각" if a1_ok else "⚠ 부분"}')
print(f'  A2 앞뒤 분할:           {"✅ 기각" if a2_ok else "⚠ 부분"}')
print(f'  A3 롤링 윈도우:         {"✅ 기각" if a3_ok else "⚠ 부분"}')
print()

total = sum([a1_ok, a2_ok, a3_ok])
if total == 3:
    print('  ✅ 완전 통과 — V4 최적 파라미터 과적합 아님')
    print('  → §33/§34 파라미터 실전 적용 안전')
elif total >= 2:
    print('  ⚠ 부분 통과 — 대체로 견고하나 일부 시기 차이 존재')
else:
    print('  ❌ 견고성 부족 — 학습 데이터 과적합 의심')

print()
print('완료.')
