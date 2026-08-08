"""_v_31_v4_recent_robustness.py — V4 최근 30일 결과의 견고성 검증

_v_30 결과 (mean +6.663%, 갭5%↑ 50.3%) 의 신뢰도를 다음 4가지로 검증:
  ① 상한가/하한가 제외 시 평균 gap
  ② 같은 기간 score==2 / score==1 / score==0 평균 (대조군)
  ③ 같은 기간 전체 보통주 평균 gap (시장 베이스라인)
  ④ score==4 의 거래대금 분포 (소형주 편향 확인)

판정 기준:
  ① 상한가 제외 후에도 mean >= +2% 이면 견고
  ② V4 시그널이 베이스라인 대비 정량적으로 우월해야
  ③ 대조군과의 정량 차이가 명확해야 (단순 강세장 효과가 아닌)
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict, Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/3] 로드...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}
recent_dates = all_dates[-31:-1]
recent_idx_set = {date_index[d] for d in recent_dates}
print(f'  검증 기간: {recent_dates[0]} ~ {recent_dates[-1]}')

t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE date >= '20251101' AND substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def v4_score(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
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
    return {'gap': gap, 'score': score, 'today_tv_won': today_tv}


print('[2/3] 점수별 + 베이스라인 측정...')
t0 = time.time()
by_score = {0: [], 1: [], 2: [], 3: [], 4: []}
all_gaps = []  # 베이스라인 (자격 통과 전체)
tv_by_score = {3: [], 4: []}  # 거래대금 분포

for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in recent_idx_set: continue
        r = v4_score(arr, row_pos)
        if r is None: continue
        by_score[r['score']].append(r['gap'])
        all_gaps.append(r['gap'])
        if r['score'] in (3, 4):
            tv_by_score[r['score']].append(r['today_tv_won'] / 1e8)
print(f'  완료: {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 분석 1: 상한가/하한가 제외
# -----------------------------------------------------------------------------
print()
print('=' * 90)
print('분석 1: 극단치 (gap >= +25% 또는 <= -25%) 제외 시')
print('=' * 90)
print(f'{"점수":<6} {"전체 N":>8} {"전체 mean":>11} {"극단치 N":>10} {"극단치 비율":>12} {"제외 후 mean":>14}')
print('-' * 90)
for s in range(5):
    arr = np.array(by_score[s]) if by_score[s] else np.array([])
    n_all = len(arr)
    if n_all == 0:
        print(f'{s:<6} {0:>8}'); continue
    mean_all = arr.mean()
    extreme_mask = (arr >= 25) | (arr <= -25)
    n_ext = extreme_mask.sum()
    inner = arr[~extreme_mask]
    mean_inner = inner.mean() if len(inner) else 0
    print(f'{s:<6} {n_all:>8,} {mean_all:>+10.3f}% {n_ext:>10,} {n_ext/n_all*100:>11.2f}% '
          f'{mean_inner:>+13.3f}%')

# -----------------------------------------------------------------------------
# 분석 2: 점수별 + 베이스라인 비교
# -----------------------------------------------------------------------------
print()
print('=' * 90)
print('분석 2: 점수별 평균 vs 베이스라인 (전체 자격 통과)')
print('=' * 90)
print(f'{"그룹":<25} {"N":>8} {"mean":>10} {"승률":>8} {"갭5%↑":>8} {"realized":>10}')
print('-' * 90)

baseline = np.array(all_gaps)
print(f'{"베이스라인 (전체)":<25} {len(baseline):>8,} {baseline.mean():>+9.3f}% '
      f'{(baseline>0).mean()*100:>7.1f}% {(baseline>=5).mean()*100:>7.2f}% '
      f'{baseline.mean() - ROUND_TRIP_COST_PCT:>+9.3f}%')

for s in range(5):
    arr = np.array(by_score[s]) if by_score[s] else np.array([])
    if len(arr) == 0: continue
    print(f'{"score == " + str(s):<25} {len(arr):>8,} {arr.mean():>+9.3f}% '
          f'{(arr>0).mean()*100:>7.1f}% {(arr>=5).mean()*100:>7.2f}% '
          f'{arr.mean()-ROUND_TRIP_COST_PCT:>+9.3f}%')

# 정량 차이
print()
s4_mean = np.array(by_score[4]).mean() if by_score[4] else 0
b_mean = baseline.mean()
print(f'  score==4 vs 베이스라인 차이: {s4_mean - b_mean:+.3f}%p')
print(f'  → V4 시그널이 단순 강세장 효과인지 판정: ', end='')
if s4_mean - b_mean > 3.0:
    print('차이 큼 (V4 효과 명확)')
elif s4_mean - b_mean > 1.0:
    print('차이 있음 (V4 효과 일부)')
else:
    print('차이 작음 (강세장 효과 의심)')


# -----------------------------------------------------------------------------
# 분석 3: 거래대금 분포 (소형주 편향 확인)
# -----------------------------------------------------------------------------
print()
print('=' * 90)
print('분석 3: 거래대금(억원) 분포 — score==4 vs score==3')
print('=' * 90)
print(f'{"score":<8} {"N":>6} {"min":>8} {"p10":>8} {"p25":>8} {"p50":>8} {"p75":>8} {"p90":>8} {"max":>10}')
print('-' * 90)
for s in (3, 4):
    if not tv_by_score[s]: continue
    arr = np.array(tv_by_score[s])
    print(f'score=={s:<3} {len(arr):>6,} '
          f'{arr.min():>7.1f}억 {np.percentile(arr,10):>7.1f}억 '
          f'{np.percentile(arr,25):>7.1f}억 {np.percentile(arr,50):>7.1f}억 '
          f'{np.percentile(arr,75):>7.1f}억 {np.percentile(arr,90):>7.1f}억 '
          f'{arr.max():>9.1f}억')

# 거래대금 100억 이상만 필터링 시 score==4 결과
print()
print('거래대금 100억 이상 score==4 만 (실전 운영 가능성):')
high_liq = [(by_score[4][i], tv_by_score[4][i]) for i in range(len(by_score[4]))
            if i < len(tv_by_score[4]) and tv_by_score[4][i] >= 100]
if high_liq:
    gaps_h = np.array([g for g, _ in high_liq])
    print(f'  N={len(high_liq)}, mean={gaps_h.mean():+.3f}%, '
          f'realized={gaps_h.mean() - ROUND_TRIP_COST_PCT:+.3f}%, '
          f'승률={(gaps_h>0).mean()*100:.1f}%, '
          f'갭5%↑={(gaps_h>=5).mean()*100:.1f}%')
else:
    print('  N=0')

# -----------------------------------------------------------------------------
# 분석 4: 보수적 전체 평가
# -----------------------------------------------------------------------------
print()
print('=' * 90)
print('최종 견고성 판정')
print('=' * 90)
arr_4 = np.array(by_score[4])
arr_4_ex = arr_4[(arr_4 < 25) & (arr_4 > -25)]
crit1 = arr_4_ex.mean() >= 2.0 if len(arr_4_ex) else False
crit2 = (arr_4.mean() - baseline.mean()) >= 2.0
crit3 = (arr_4 >= 5).mean() >= 0.20

print(f'  ① 극단치 제외 평균 >= +2.0%: {"✅" if crit1 else "❌"} '
      f'({arr_4_ex.mean():+.3f}%, N={len(arr_4_ex)})')
print(f'  ② 베이스라인 대비 +2.0%p 우위: {"✅" if crit2 else "❌"} '
      f'(차이 {arr_4.mean()-baseline.mean():+.3f}%p)')
print(f'  ③ 갭 5%↑ 비율 >= 20%:        {"✅" if crit3 else "❌"} '
      f'({(arr_4 >= 5).mean()*100:.1f}%)')
print()
total = sum([crit1, crit2, crit3])
if total == 3:
    print('✅ V4 시그널 견고성 검증 통과 — 백테스트 결과 신뢰 가능')
elif total >= 2:
    print('⚠ 부분 통과 — 일부 견고성 결함, 운영 시 주의')
else:
    print('❌ 견고성 미달 — 추가 분석 필요')

print()
print('완료.')
