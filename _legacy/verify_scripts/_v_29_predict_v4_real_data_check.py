"""_v_29_predict_v4_real_data_check.py — V4 패치 설계서 실데이터 정합성 검증

목적:
  _v_26 의 numpy 기반 V4 계산 (sample 148일 × 3,361종목 = 193,708건)과
  설계서의 pandas DataFrame 기반 predict_v4() 가
  동일 데이터에서 동일 점수 분포를 산출하는지 확인.

판정:
  ① score 분포 (0/1/2/3/4) 가 _v_26 과 정확 일치
  ② score==4 카운트 = 616
  ③ 격리 클래스 결과 = numpy 결과 (1:1 매칭)
"""
import sqlite3
import numpy as np
import pandas as pd
import time
from collections import defaultdict, Counter
import sys
sys.path.insert(0, r'D:\StockAnalyst')
from _v_28_predict_v4_dry_run import GapUpPredictorV4Patch

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/3] 로드...')
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
print(f'  샘플: {len(samples)}')

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
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()

# -----------------------------------------------------------------------------
# numpy 기반 V4 (=_v_26 의 V4 부분 그대로)
# -----------------------------------------------------------------------------
def v4_numpy(arr, t_pos):
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
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
    return int(cond1) + int(cond2) + int(cond3) + int(cond4)


# -----------------------------------------------------------------------------
# pandas 기반 (predict_v4 가 받는 형식: 'Open'/'High'/'Low'/'Close'/'Volume')
# -----------------------------------------------------------------------------
def to_df_at(arr, t_pos, lookback=70):
    """t_pos 기준 lookback 만큼의 데이터를 pandas DataFrame으로"""
    start = max(0, t_pos - lookback + 1)
    end = t_pos + 1
    sub = arr[start:end]
    return pd.DataFrame({
        'Open':   sub[:,1],
        'High':   sub[:,2],
        'Low':    sub[:,3],
        'Close':  sub[:,4],
        'Volume': sub[:,5],
    })


print('[2/3] V4 점수 사전 검증 (전 샘플) — numpy vs predict_v4...')
t0 = time.time()
predictor = GapUpPredictorV4Patch()

numpy_scores = []
pandas_scores = []
mismatches = []

for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        s_np = v4_numpy(arr, row_pos)
        if s_np is None: continue
        # numpy 통과 케이스만 pandas 비교
        df = to_df_at(arr, row_pos, lookback=70)
        if len(df) < 60:
            continue
        r = predictor.predict_v4(code, df)
        s_pd = r['v4_score']
        numpy_scores.append(s_np)
        pandas_scores.append(s_pd)
        if s_np != s_pd:
            mismatches.append((code, all_dates[date_idx], s_np, s_pd, r['v4_conditions']))

print(f'  비교 완료: {len(numpy_scores):,}건, {time.time()-t0:.1f}초')


# -----------------------------------------------------------------------------
# [3/3] 결과 비교
# -----------------------------------------------------------------------------
print()
print('=' * 70)
print('[3/3] 결과 비교')
print('=' * 70)

np_dist = Counter(numpy_scores)
pd_dist = Counter(pandas_scores)

print(f'\n점수 분포 (총 {len(numpy_scores):,}건):')
print(f'{"score":>6} {"numpy":>10} {"pandas":>10} {"diff":>8}')
print('-' * 40)
for s in range(5):
    n = np_dist.get(s, 0)
    p = pd_dist.get(s, 0)
    print(f'{s:>6} {n:>10,} {p:>10,} {p-n:>+7,}')

print()
print(f'_v_26 결과 (참조): score==4 = 616, score==3 = 1,938, score==2 = 7,739')
print(f'이번 측정:       score==4 = {np_dist.get(4, 0):,}, score==3 = {np_dist.get(3, 0):,}, score==2 = {np_dist.get(2, 0):,}')

print()
print(f'mismatch (numpy != pandas): {len(mismatches)}건')
if mismatches:
    print('\n첫 5건 샘플:')
    for code, date, s_np, s_pd, conds in mismatches[:5]:
        print(f'  {code} @ {date}: numpy={s_np}, pandas={s_pd}, conds={conds}')

# 판정
ok_distribution = (np_dist == pd_dist)
ok_count_4 = (np_dist.get(4, 0) == 616 and pd_dist.get(4, 0) == 616)
ok_no_mismatch = (len(mismatches) == 0)

print()
print('=' * 70)
print('최종 판정')
print('=' * 70)
print(f'  분포 일치 (numpy == pandas): {"✅" if ok_distribution else "❌"}')
print(f'  score==4 = 616 (_v_26 참조): {"✅" if ok_count_4 else "❌"}')
print(f'  per-row mismatch 0건:         {"✅" if ok_no_mismatch else f"❌ ({len(mismatches)}건)"}')

if ok_distribution and ok_count_4 and ok_no_mismatch:
    print()
    print('✅ V4 패치 설계서 = _v_26 numpy 결과와 완전 일치')
    print('   → closing_bet_unified.py 패치 시 백테스트 결과 (_v_27) 그대로 재현 보장')
else:
    print()
    print('❌ 정합성 결함 — 설계 재검토 필요')

print()
print('완료.')
