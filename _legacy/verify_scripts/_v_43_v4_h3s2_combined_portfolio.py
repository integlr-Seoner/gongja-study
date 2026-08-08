"""_v_43_v4_h3s2_combined_portfolio.py — V4 × H3+S2 결합 포트폴리오 백테스트

목적:
  두 전략의 결합 효과 실측:
  1. 상관계수 (진짜 분산 효과 있는지)
  2. 결합 시 Sharpe / CAGR 변화
  3. 월별 안정성

측정 방식:
  - V4: 매 샘플일(월별)의 score==4 종목 평균 realized (가중치 동일)
        실전에 가깝도록 운영 30%, 종목당 5%, max 30 포지션 제약 반영
  - H3+S2: 기존 로직 그대로
  - 비중: 50% V4, 20% H3+S2, 30% 현금 (§31 권고)
  - 현금: 수익률 0% 가정 (보수적)

측정 기간: 2014~2026 (13년), 월별 리밸런싱
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

# 포트폴리오 비중 (§31 권고)
W_V4 = 0.50
W_H3S2 = 0.20
W_CASH = 0.30

# V4 운영 제약
WORKING_RATIO_V4 = 0.30   # V4 자본 중 30% 만 실투입
PER_STOCK_MAX = 0.05       # 종목당 5% (V4 자본 대비)
MAX_POS = 30

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()


print('[1/5] 지수 로드 + 리밸런싱 시점...')
kospi = cur.execute(
    "SELECT date, close FROM daily_index_long WHERE symbol='KOSPI' "
    "AND date >= '20140101' ORDER BY date"
).fetchall()
kosdaq = cur.execute(
    "SELECT date, close FROM daily_index_long WHERE symbol='KOSDAQ' "
    "AND date >= '20140101' ORDER BY date"
).fetchall()
kospi_dict = {d: c for d, c in kospi}
kosdaq_dict = {d: c for d, c in kosdaq}
common_dates = sorted(set(kospi_dict.keys()) & set(kosdaq_dict.keys()))
kospi_c = np.array([kospi_dict[d] for d in common_dates])
kosdaq_c = np.array([kosdaq_dict[d] for d in common_dates])
n = len(common_dates)
date_index = {d: i for i, d in enumerate(common_dates)}

# 월별 리밸런싱 시점 (상관계수 60일 필요 → min_idx=60)
month_pts = []; cy = ''
for i, d in enumerate(common_dates):
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        month_pts.append(i); cy = ym
month_pts = [p for p in month_pts if p >= 60 and p + 20 < n]
print(f'  리밸런싱 시점: {len(month_pts)}회')


# [2/5] V4 score==4 측정 (월별)
print('\n[2/5] V4 score==4 월별 측정...')
all_dates_ohlcv = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_idx_ohlcv = {d: i for i, d in enumerate(all_dates_ohlcv)}

t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_idx_ohlcv.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  OHLCV: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def v4_at(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    close_t = c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    ma5 = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - o[t_pos]; rng = h[t_pos] - lo[t_pos]
    cond1 = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    cond2 = h[t_pos] > h[t_pos-60:t_pos].max()
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    today_tv = close_t * vol_t
    cond3 = tv_arr.mean() > 0 and (today_tv / tv_arr.mean() >= 3.0)
    cond4 = (rng > 0) and ((close_t - lo[t_pos]) / rng >= 0.95)
    score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    return {'gap': gap, 'score': score} if score == 4 else None


# 리밸런싱 일자 (common_dates 기준) → OHLCV 일자로 매핑
# 매 달 15일 이후 첫 영업일을 샘플로
sample_ohlcv_dates = []
cy = ''
for d in all_dates_ohlcv:
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        sample_ohlcv_dates.append(d); cy = ym
sample_idx_set = {date_idx_ohlcv[d] for d in sample_ohlcv_dates
                  if d in date_idx_ohlcv}

print(f'  V4 샘플 일자: {len(sample_ohlcv_dates)}개')

# 각 샘플 일자별 score==4 종목들의 gap 리스트 수집
t0 = time.time()
v4_by_date = defaultdict(list)  # date → [gap1, gap2, ...]
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = v4_at(arr, row_pos)
        if r is None: continue
        date_str = all_dates_ohlcv[date_idx]
        v4_by_date[date_str].append(r['gap'])
print(f'  V4 측정 완료: {sum(len(v) for v in v4_by_date.values())}건 발견, {time.time()-t0:.1f}초')

# 월별 V4 실전 수익 계산 (운영 제약 반영)
# 총 자본 1 기준:
#   WORKING = 0.30 중 min(N종목, 30) * 0.05 만 실투입, 나머지 현금 (수익 0)
#   N종목 평균 gap 수익 (realized = gap - ROUND_TRIP_COST_PCT)
v4_monthly_returns = {}
for date_str, gaps in v4_by_date.items():
    n_stocks = len(gaps)
    if n_stocks == 0:
        v4_monthly_returns[date_str] = 0.0
        continue
    actual_n = min(n_stocks, MAX_POS)
    invested_ratio = actual_n * PER_STOCK_MAX  # 종목당 5%
    invested_ratio = min(invested_ratio, WORKING_RATIO_V4)  # 운용 30% 상한
    
    # 평균 realized (gap 평균 - 비용)
    mean_gap = np.mean(gaps[:actual_n])
    mean_realized = mean_gap - ROUND_TRIP_COST_PCT
    
    # 자본 전체 수익률
    monthly_ret = invested_ratio * (mean_realized / 100)
    v4_monthly_returns[date_str] = monthly_ret

# 발생 안 한 달은 0
for d in sample_ohlcv_dates:
    if d not in v4_monthly_returns:
        v4_monthly_returns[d] = 0.0

print(f'  V4 월별 수익 계산: {len(v4_monthly_returns)}개월')


# [3/5] H3+S2 월별 수익 (기존 로직)
print('\n[3/5] H3+S2 월별 수익 계산...')

def rolling_corr(i, days):
    if i < days: return None
    k = kospi_c[i-days:i+1]; q = kosdaq_c[i-days:i+1]
    kr = np.diff(k) / k[:-1]; qr = np.diff(q) / q[:-1]
    if kr.std() == 0 or qr.std() == 0: return None
    return float(np.corrcoef(kr, qr)[0, 1])

h3s2_monthly_returns = {}
for i in month_pts:
    corr = rolling_corr(i, 60)
    if corr is not None and corr > 0.80:
        choice = 'EQUAL'
    else:
        k20 = (kospi_c[i] / kospi_c[i-20] - 1) * 100
        q20 = (kosdaq_c[i] / kosdaq_c[i-20] - 1) * 100
        sp = k20 - q20
        if sp > 3: choice = 'KOSDAQ'
        elif sp < -3: choice = 'KOSPI'
        else: choice = 'EQUAL'
    r_k = kospi_c[i+20] / kospi_c[i] - 1
    r_q = kosdaq_c[i+20] / kosdaq_c[i] - 1
    if choice == 'KOSPI': r = r_k
    elif choice == 'KOSDAQ': r = r_q
    else: r = (r_k + r_q) / 2
    h3s2_monthly_returns[common_dates[i]] = r

print(f'  H3+S2 월별 수익: {len(h3s2_monthly_returns)}개월')


# [4/5] 날짜 매핑 — V4 sample_ohlcv_dates 와 H3+S2 common_dates 다름
# 가장 가까운 날짜로 매핑 (같은 달 기준)
print('\n[4/5] 날짜 매핑 + 결합 포트폴리오 계산...')

def yyyymm(d): return d[:6]

h3s2_by_month = {}
for d, r in h3s2_monthly_returns.items():
    h3s2_by_month[yyyymm(d)] = r

v4_by_month = {}
for d, r in v4_monthly_returns.items():
    v4_by_month[yyyymm(d)] = r

common_months = sorted(set(v4_by_month.keys()) & set(h3s2_by_month.keys()))
print(f'  공통 월: {len(common_months)}개월')

# 각 월의 [V4, H3S2, 결합] 수익률
v4_rets = np.array([v4_by_month[m] for m in common_months])
h3s2_rets = np.array([h3s2_by_month[m] for m in common_months])
combined_rets = W_V4 * v4_rets + W_H3S2 * h3s2_rets  # 현금(30%)은 0%


# [5/5] 성과 비교
print()
print('=' * 100)
print('[5/5] 성과 비교 (월별 수익 기준)')
print('=' * 100)

def stats(rets, ppy=12):
    if len(rets) == 0:
        return {'cagr': 0, 'mdd': 0, 'sharpe': 0, 'mean': 0, 'std': 0}
    cum = np.prod(1 + rets) - 1
    yrs = len(rets) / ppy
    cagr = ((1 + cum) ** (1/yrs) - 1) * 100 if yrs > 0 and cum > -1 else 0
    cp = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cp)
    dd = (cp - peak) / peak
    return {'cagr': cagr, 'mdd': dd.min() * 100,
            'sharpe': (rets.mean() * 100) / (rets.std() * 100) if rets.std() > 0 else 0,
            'mean': rets.mean() * 100, 'std': rets.std() * 100,
            'cum': cum * 100, 'n': len(rets)}

# 단독 vs 결합
v4_s = stats(v4_rets)
h3s2_s = stats(h3s2_rets)
comb_s = stats(combined_rets)

# V4 단독 (전량 투자 가정): v4_rets 에 자본 비중 곱하지 않은 값
v4_solo = v4_rets * (1 / W_V4) if W_V4 > 0 else v4_rets  # 원래 전량 기준으로 복원
v4_solo_capped = np.clip(v4_solo, -0.5, 0.5)  # 극단값 제한
v4_solo_s = stats(v4_solo_capped)

# H3+S2 단독 (전량)
h3s2_solo = h3s2_rets * (1 / W_H3S2) if W_H3S2 > 0 else h3s2_rets
h3s2_solo_capped = np.clip(h3s2_solo, -0.5, 0.5)
h3s2_solo_s = stats(h3s2_solo_capped)

print(f'{"전략":<35} {"N":>5} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} {"평균/월":>9} {"std":>8}')
print('-' * 100)
print(f'{"V4 단독 (전량)":<35} {v4_solo_s["n"]:>5} {v4_solo_s["cagr"]:>+8.2f}% '
      f'{v4_solo_s["mdd"]:>+8.2f}% {v4_solo_s["sharpe"]:>8.3f} {v4_solo_s["mean"]:>+8.3f}% {v4_solo_s["std"]:>7.3f}%')
print(f'{"H3+S2 단독 (전량)":<35} {h3s2_solo_s["n"]:>5} {h3s2_solo_s["cagr"]:>+8.2f}% '
      f'{h3s2_solo_s["mdd"]:>+8.2f}% {h3s2_solo_s["sharpe"]:>8.3f} {h3s2_solo_s["mean"]:>+8.3f}% {h3s2_solo_s["std"]:>7.3f}%')
print(f'{"V4 기여 (W=50%)":<35} {v4_s["n"]:>5} {v4_s["cagr"]:>+8.2f}% '
      f'{v4_s["mdd"]:>+8.2f}% {v4_s["sharpe"]:>8.3f} {v4_s["mean"]:>+8.3f}% {v4_s["std"]:>7.3f}%')
print(f'{"H3+S2 기여 (W=20%)":<35} {h3s2_s["n"]:>5} {h3s2_s["cagr"]:>+8.2f}% '
      f'{h3s2_s["mdd"]:>+8.2f}% {h3s2_s["sharpe"]:>8.3f} {h3s2_s["mean"]:>+8.3f}% {h3s2_s["std"]:>7.3f}%')
print(f'{"★ 결합 포트폴리오 (50+20+30현금)":<35} {comb_s["n"]:>5} {comb_s["cagr"]:>+8.2f}% '
      f'{comb_s["mdd"]:>+8.2f}% {comb_s["sharpe"]:>8.3f} {comb_s["mean"]:>+8.3f}% {comb_s["std"]:>7.3f}%')


# 상관관계 분석
print()
print('=' * 100)
print('[상관관계] V4 월별 수익 vs H3+S2 월별 수익')
print('=' * 100)
corr_vh = np.corrcoef(v4_rets, h3s2_rets)[0, 1]
print(f'  V4 vs H3+S2 상관계수: {corr_vh:+.4f}')

if corr_vh < 0.15:
    print(f'  ✅ 상관관계 매우 낮음 — 분산 효과 명확')
elif corr_vh < 0.35:
    print(f'  ✅ 상관관계 낮음 — 분산 효과 양호')
elif corr_vh < 0.55:
    print(f'  ⚠ 중간 상관관계 — 분산 효과 제한적')
else:
    print(f'  ❌ 높은 상관관계 — 분산 효과 작음')

# 같은 방향 vs 반대 방향 월 비율
same_sign = np.sum(np.sign(v4_rets) == np.sign(h3s2_rets))
diff_sign = len(v4_rets) - same_sign
print(f'\n  같은 방향 월 (둘 다 양수 or 둘 다 음수): {same_sign}/{len(v4_rets)} ({same_sign/len(v4_rets)*100:.1f}%)')
print(f'  반대 방향 월: {diff_sign}/{len(v4_rets)} ({diff_sign/len(v4_rets)*100:.1f}%)')


# 연도별 안정성
print()
print('=' * 100)
print('[연도별 안정성] 결합 포트폴리오')
print('=' * 100)
yearly = defaultdict(list)
for m, r in zip(common_months, combined_rets):
    yearly[m[:4]].append(r)

print(f'{"연도":<6} {"개월":>5} {"연수익":>10} {"월평균":>10} {"월 최고":>10} {"월 최저":>10} {"월승률":>8}')
print('-' * 100)
for yr in sorted(yearly.keys()):
    rs = np.array(yearly[yr])
    yr_ret = (np.prod(1 + rs) - 1) * 100
    mean_m = rs.mean() * 100
    max_m = rs.max() * 100
    min_m = rs.min() * 100
    win = (rs > 0).mean() * 100
    print(f'{yr:<6} {len(rs):>5} {yr_ret:>+9.2f}% {mean_m:>+9.3f}% {max_m:>+9.3f}% '
          f'{min_m:>+9.3f}% {win:>7.1f}%')


# 벤치마크 비교 (KOSPI 단순 보유 + 현금 30%)
print()
print('=' * 100)
print('[벤치마크 비교]')
print('=' * 100)

# KOSPI 단순 보유 (월별 수익)
kospi_monthly = []
for m in common_months:
    # 해당 월의 대표일 (15일 이후 첫 영업일)
    for d in common_dates:
        if d[:6] == m and int(d[6:]) >= 15:
            i = date_index[d]
            if i + 20 < n:
                r = kospi_c[i+20] / kospi_c[i] - 1
                kospi_monthly.append(r)
            break
    else:
        kospi_monthly.append(0)
kospi_monthly = np.array(kospi_monthly)
kospi_50cash = 0.70 * kospi_monthly  # 70% KOSPI + 30% 현금 (결합과 같은 실투입률이 아니지만 참조)

k_s = stats(kospi_monthly)
k70_s = stats(kospi_50cash)

print(f'{"벤치":<35} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8}')
print('-' * 100)
print(f'{"KOSPI 100%":<35} {k_s["cagr"]:>+8.2f}% {k_s["mdd"]:>+8.2f}% {k_s["sharpe"]:>8.3f}')
print(f'{"KOSPI 70% + 현금 30%":<35} {k70_s["cagr"]:>+8.2f}% {k70_s["mdd"]:>+8.2f}% {k70_s["sharpe"]:>8.3f}')
print(f'{"★ V4+H3S2 결합 (50+20+30현금)":<35} {comb_s["cagr"]:>+8.2f}% {comb_s["mdd"]:>+8.2f}% {comb_s["sharpe"]:>8.3f}')
print(f'\n  결합 vs KOSPI100%: CAGR {comb_s["cagr"] - k_s["cagr"]:+.2f}%p, '
      f'MDD {comb_s["mdd"] - k_s["mdd"]:+.2f}%p')
print(f'  결합 vs KOSPI70%현금30%: CAGR {comb_s["cagr"] - k70_s["cagr"]:+.2f}%p, '
      f'MDD {comb_s["mdd"] - k70_s["mdd"]:+.2f}%p')


# 비중 변경 민감도 — V4 비중을 40/50/60% 변화시키며
print()
print('=' * 100)
print('[비중 민감도] V4 비중 조정 시 결합 성과')
print('=' * 100)
print(f'{"V4 비중":<10} {"H3+S2 비중":<12} {"현금":<10} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8}')
print('-' * 100)

scenarios = [
    (0.30, 0.20, 0.50), (0.40, 0.20, 0.40),
    (0.50, 0.20, 0.30), (0.60, 0.20, 0.20),
    (0.50, 0.30, 0.20), (0.70, 0.30, 0.00),
]
for wv4, wh, wc in scenarios:
    c_rets = wv4 * v4_rets + wh * h3s2_rets  # 현금 0
    s = stats(c_rets)
    tag = ' ← 권고' if (wv4, wh, wc) == (0.50, 0.20, 0.30) else ''
    print(f'{wv4*100:.0f}%{"":<6} {wh*100:.0f}%{"":<8} {wc*100:.0f}%{"":<6} '
          f'{s["cagr"]:>+8.2f}% {s["mdd"]:>+8.2f}% {s["sharpe"]:>8.3f}{tag}')


print()
print('완료.')
