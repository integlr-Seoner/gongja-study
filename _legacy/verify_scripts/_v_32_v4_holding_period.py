"""_v_32_v4_holding_period.py — V4 시그널 다중 보유기간 수익률 분석

목적:
  V4 시그널이 T+1일 갭만 좋은지, 아니면 T+5/T+20까지도 우수한지 검증.
  중기 보유 가치 평가 + 시그널 활용 다각화 가능성 탐색.

측정:
  - gap     (T0.close → T+1.open) — 기존 종가배팅
  - ret_1d  (T0.close → T+1.close)
  - ret_5d  (T0.close → T+5.close)
  - ret_20d (T0.close → T+20.close)
  - mdd_5d  (T+1~T+5 중 최대 낙폭)
  - mfe_5d  (T+1~T+5 중 최대 상승)

판정:
  ① 모든 보유기간에서 score 단조 증가
  ② T+5, T+20까지 score==4 의 realized 양수 유지
  ③ MDD vs MFE 비율로 보유 위험도 평가
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

print('[1/4] 거래일 + 샘플 결정...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' AND date <= '20260417' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
samples = []; cy = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != cy and dd >= 15:
        samples.append(d); cy = ym
sample_idx_set = {date_index[d] for d in samples if d in date_index}
print(f'  거래일: {len(all_dates):,}, 샘플: {len(samples)}')

print('[2/4] OHLCV 로드...')
t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 81: continue  # T+20까지 필요해서 최소 81일
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


# -----------------------------------------------------------------------------
# V4 점수 + 다중 보유기간 측정
# -----------------------------------------------------------------------------
def measure(arr, t_pos):
    """T0 기준 score + ret_1d/5d/20d + mdd_5d/mfe_5d 동시 계산
    
    데이터 부족 시 None 반환 (T+20 까지 필요).
    """
    if t_pos < 60 or t_pos + 20 >= len(arr): return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    
    if close_t <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    
    # 연속 거래일 체크 (T+1 ~ T+20 모두 연속)
    base_idx = int(arr[t_pos, 0])
    for k in range(1, 21):
        if int(arr[t_pos+k, 0]) != base_idx + k:
            return None
    
    # 각 시점 종가
    open_t1 = o[t_pos+1]
    close_t1 = c[t_pos+1]
    close_t5 = c[t_pos+5]
    close_t20 = c[t_pos+20]
    if open_t1 <= 0 or close_t1 <= 0 or close_t5 <= 0 or close_t20 <= 0:
        return None
    
    # 수익률 계산
    gap = (open_t1 / close_t - 1) * 100
    ret_1d = (close_t1 / close_t - 1) * 100
    ret_5d = (close_t5 / close_t - 1) * 100
    ret_20d = (close_t20 / close_t - 1) * 100
    
    # T+1~T+5 MDD/MFE (close 기준)
    closes_1to5 = c[t_pos+1:t_pos+6]
    mdd_5d = ((closes_1to5.min() / close_t) - 1) * 100
    mfe_5d = ((closes_1to5.max() / close_t) - 1) * 100
    
    # V4 점수 (_v_26 동일)
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t; rng = high_t - low_t
    cond1 = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    cond2 = high_t > h[t_pos-60:t_pos].max()
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    cond3 = (avg20 > 0) and (today_tv / avg20 >= 3.0)
    cond4 = (rng > 0) and ((close_t - low_t) / rng >= 0.95)
    score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    
    return {
        'score': score,
        'gap': gap, 'ret_1d': ret_1d, 'ret_5d': ret_5d, 'ret_20d': ret_20d,
        'mdd_5d': mdd_5d, 'mfe_5d': mfe_5d,
    }


print('[3/4] 점수 + 보유기간 수익률 계산...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = measure(arr, row_pos)
        if r is None: continue
        records.append(r)
print(f'  완료: {len(records):,}건, {time.time()-t0:.1f}초')


# -----------------------------------------------------------------------------
# 4. 결과 출력
# -----------------------------------------------------------------------------
arr_data = {
    'gap':     np.array([r['gap']     for r in records]),
    'ret_1d':  np.array([r['ret_1d']  for r in records]),
    'ret_5d':  np.array([r['ret_5d']  for r in records]),
    'ret_20d': np.array([r['ret_20d'] for r in records]),
    'mdd_5d':  np.array([r['mdd_5d']  for r in records]),
    'mfe_5d':  np.array([r['mfe_5d']  for r in records]),
}
scores = np.array([r['score'] for r in records])

print()
print('=' * 110)
print('[4/4] V4 점수별 다중 보유기간 수익률 분석')
print('=' * 110)
print(f'{"score":>6} {"N":>8} | {"gap":>10} {"ret_1d":>10} {"ret_5d":>10} {"ret_20d":>10} | {"mdd_5d":>10} {"mfe_5d":>10}')
print('-' * 110)

stats_table = []
for s in range(5):
    mask = scores == s
    n = mask.sum()
    if n < 5:
        continue
    row = {'score': s, 'N': int(n)}
    for k in ['gap', 'ret_1d', 'ret_5d', 'ret_20d', 'mdd_5d', 'mfe_5d']:
        row[k + '_mean'] = arr_data[k][mask].mean()
        row[k + '_std'] = arr_data[k][mask].std()
    stats_table.append(row)
    print(f'{s:>6} {n:>8,} | '
          f'{row["gap_mean"]:>+9.3f}% {row["ret_1d_mean"]:>+9.3f}% '
          f'{row["ret_5d_mean"]:>+9.3f}% {row["ret_20d_mean"]:>+9.3f}% | '
          f'{row["mdd_5d_mean"]:>+9.3f}% {row["mfe_5d_mean"]:>+9.3f}%')

# 단조 증가성 검사
print()
print('=' * 110)
print('단조 증가성 (점수↑ → 수익↑)')
print('=' * 110)
for k in ['gap', 'ret_1d', 'ret_5d', 'ret_20d']:
    means = [r[k + '_mean'] for r in stats_table]
    inversions = sum(1 for i in range(1, len(means)) if means[i] - means[i-1] < -0.05)
    monotone = '✅ 완벽' if inversions == 0 else f'⚠ 역전 {inversions}회'
    diffs = [f'{means[i]-means[i-1]:+.2f}%p' for i in range(1, len(means))]
    print(f'  {k:<10} 0→4 변화: {means[0]:+.2f}% → ... → {means[-1]:+.2f}% '
          f'({monotone}, 단계: {", ".join(diffs)})')


# -----------------------------------------------------------------------------
# 5. 표준편차 (변동성) + Sharpe 유사 지표
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('변동성 분석 (표준편차) + 단순 Sharpe (mean / std)')
print('=' * 110)
print(f'{"score":>6} | {"ret_1d":>22} | {"ret_5d":>22} | {"ret_20d":>22}')
print(f'{"":>6} | {"std":>10} {"sharpe":>10} | {"std":>10} {"sharpe":>10} | {"std":>10} {"sharpe":>10}')
print('-' * 110)
for r in stats_table:
    sh1d = r['ret_1d_mean'] / r['ret_1d_std'] if r['ret_1d_std'] > 0 else 0
    sh5d = r['ret_5d_mean'] / r['ret_5d_std'] if r['ret_5d_std'] > 0 else 0
    sh20d = r['ret_20d_mean'] / r['ret_20d_std'] if r['ret_20d_std'] > 0 else 0
    print(f'{r["score"]:>6} | '
          f'{r["ret_1d_std"]:>9.3f}% {sh1d:>10.3f} | '
          f'{r["ret_5d_std"]:>9.3f}% {sh5d:>10.3f} | '
          f'{r["ret_20d_std"]:>9.3f}% {sh20d:>10.3f}')

# -----------------------------------------------------------------------------
# 6. score==4 의 보유기간별 승률
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('score==4 의 보유기간별 승률 + realized')
print('=' * 110)
mask4 = scores == 4
print(f'{"보유기간":<12} {"평균%":>10} {"승률%":>8} {"realized%":>12} {"중간값%":>10} {"std":>9}')
print('-' * 110)
for k, label in [('gap', 'T+1 갭'), ('ret_1d', 'T+1 종가'),
                  ('ret_5d', 'T+5 종가'), ('ret_20d', 'T+20 종가')]:
    arr = arr_data[k][mask4]
    if len(arr) == 0: continue
    mean = arr.mean()
    win = (arr > 0).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    med = np.median(arr)
    std = arr.std()
    print(f'{label:<12} {mean:>+9.3f}% {win:>7.1f}% {real:>+11.3f}% {med:>+9.3f}% {std:>8.3f}%')

# -----------------------------------------------------------------------------
# 7. score==4 의 MDD/MFE 분포
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('score==4 의 T+1~T+5 손실/이익 폭 분포')
print('=' * 110)
mdd = arr_data['mdd_5d'][mask4]
mfe = arr_data['mfe_5d'][mask4]
print(f'{"지표":<15} {"평균":>10} {"중간값":>10} {"p10":>10} {"p25":>10} {"p75":>10} {"p90":>10}')
print('-' * 110)
print(f'{"MDD (낙폭)":<15} {mdd.mean():>+9.3f}% {np.median(mdd):>+9.3f}% '
      f'{np.percentile(mdd,10):>+9.3f}% {np.percentile(mdd,25):>+9.3f}% '
      f'{np.percentile(mdd,75):>+9.3f}% {np.percentile(mdd,90):>+9.3f}%')
print(f'{"MFE (상승폭)":<15} {mfe.mean():>+9.3f}% {np.median(mfe):>+9.3f}% '
      f'{np.percentile(mfe,10):>+9.3f}% {np.percentile(mfe,25):>+9.3f}% '
      f'{np.percentile(mfe,75):>+9.3f}% {np.percentile(mfe,90):>+9.3f}%')
print(f'  → MFE/|MDD| 비율 (이익/손실): {mfe.mean() / abs(mdd.mean()):.2f}')


# -----------------------------------------------------------------------------
# 8. 최적 보유기간 결정
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('score==4 최적 보유기간 결정 (수익 / 변동성 기준)')
print('=' * 110)

mask4 = scores == 4
periods = [
    ('T+1 갭 (종가배팅)', 'gap'),
    ('T+1 종가',          'ret_1d'),
    ('T+5 종가',          'ret_5d'),
    ('T+20 종가',         'ret_20d'),
]

print(f'{"보유기간":<22} {"realized":>11} {"std":>9} {"sharpe-like":>12} {"승률":>8} {"판정":<25}')
print('-' * 110)
best = None
best_sharpe = -999
for label, key in periods:
    arr = arr_data[key][mask4]
    real = arr.mean() - ROUND_TRIP_COST_PCT
    std = arr.std()
    sh = real / std if std > 0 else 0
    win = (arr > 0).mean() * 100
    print(f'{label:<22} {real:>+10.3f}% {std:>8.3f}% {sh:>12.4f} {win:>7.1f}% ', end='')
    if real > 0 and sh > best_sharpe:
        best_sharpe = sh
        best = label
        print('← 최고 sharpe 후보')
    elif real <= 0:
        print('(realized 음수)')
    else:
        print('')

print()
print(f'최적 보유기간 (수익/변동성 기준): {best if best else "없음"}')

# -----------------------------------------------------------------------------
# 9. 종합 판정
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('종합 판정')
print('=' * 110)
mask4 = scores == 4
all_real_positive = all(
    arr_data[k][mask4].mean() - ROUND_TRIP_COST_PCT > 0
    for k in ['gap', 'ret_1d', 'ret_5d', 'ret_20d']
)
mono_check = []
for k in ['gap', 'ret_1d', 'ret_5d', 'ret_20d']:
    means = [arr_data[k][scores==s].mean() if (scores==s).sum() >= 5 else 0
             for s in range(5)]
    invs = sum(1 for i in range(1, len(means)) if means[i] - means[i-1] < -0.05)
    mono_check.append((k, invs))

print(f'  ① 모든 보유기간 realized 양수: {"✅" if all_real_positive else "❌"}')
print(f'  ② 단조 증가성 (역전 횟수):')
for k, invs in mono_check:
    print(f'     {k}: {"✅" if invs == 0 else f"⚠ {invs}회 역전"}')

print()
print('완료.')
