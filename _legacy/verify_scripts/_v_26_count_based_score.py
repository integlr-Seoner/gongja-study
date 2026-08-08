"""_v_26_count_based_score.py — 카운트 기반 점수 시스템 다중 변형 검증

_v_25 결과: 가중치 합산 방식은 [60-65) 새 역전 발생.
가설: 조건 합산 자체가 구조적 결함. 카운트 방식이 더 강건.

5가지 변형 동시 비교:
  V1 (최소 4조건):  align+big / new_high / tv2x / pos85
  V2 (모순배제):    V1 + 신고가시 눌림목 무시, 없으면 눌림목 인정 → 0~5
  V3 (가중):        핵심 4조건 1점, 신고가 2점 → 0~5
  V4 (스트릭트):    align+big / new_high / tv3x / pos95 → 0~4
  V5 (TV-P 페어):   align+big / new_high / (tv2x AND pos85) → 0~3

판정 기준:
  ① 단조 증가성 (점수 ↑ → realized ↑ 일관)
  ② Sweet spot 명확성 (최강 점수 구간의 N과 realized)
  ③ 컷오프 활용성 (실전 진입 가능 N 규모)
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
print(f'  완료: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def multi_score(arr, t_pos):
    """5가지 변형 점수 동시 계산."""
    if t_pos < 60 or t_pos + 1 >= len(arr): return None
    if int(arr[t_pos+1, 0]) != int(arr[t_pos, 0]) + 1: return None
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    open_t, high_t = o[t_pos], h[t_pos]
    low_t, close_t = lo[t_pos], c[t_pos]; vol_t = v[t_pos]
    open_t1 = o[t_pos+1]
    if close_t <= 0 or open_t1 <= 0 or close_t < MIN_PRICE or vol_t < MIN_VOL:
        return None
    gap = (open_t1 / close_t - 1) * 100
    
    # 조건 플래그 계산
    ma5  = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    has_align = (ma5 > ma10) and (ma10 > ma20)
    body = close_t - open_t; rng = high_t - low_t
    has_align_big = has_align and rng > 0 and body > 0 and (body / rng > 0.6)
    
    prev60_high = h[t_pos-60:t_pos].max()
    has_new_high = high_t > prev60_high
    
    recent_high = h[t_pos-9:t_pos+1].max()
    recent_low  = lo[t_pos-4:t_pos+1].min()
    pullback = (recent_high - recent_low) / recent_high * 100 if recent_high > 0 else 0
    today_up = close_t > c[t_pos-1]
    has_pullback = (5 <= pullback <= 15) and today_up
    
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20 = tv_arr.mean()
    today_tv = close_t * vol_t
    tv_ratio = today_tv / avg20 if avg20 > 0 else 0
    has_tv_2x = tv_ratio >= 2.0
    has_tv_3x = tv_ratio >= 3.0
    
    close_pos = (close_t - low_t) / rng if rng > 0 else 0
    has_pos_85 = close_pos >= 0.85
    has_pos_95 = close_pos >= 0.95
    
    # ---------- V1: 최소 4조건 ----------
    v1 = sum([has_align_big, has_new_high, has_tv_2x, has_pos_85])
    
    # ---------- V2: 모순 배제 (신고가시 눌림목 무시) ----------
    # 5조건: align_big / new_high / tv2x / pos85 / (pullback BUT NOT new_high)
    pullback_valid = has_pullback and not has_new_high
    v2 = sum([has_align_big, has_new_high, has_tv_2x, has_pos_85, pullback_valid])
    
    # ---------- V3: 가중 (신고가 2점) ----------
    v3 = sum([has_align_big, has_tv_2x, has_pos_85]) + (2 if has_new_high else 0)
    
    # ---------- V4: 스트릭트 (강한 조건) ----------
    v4 = sum([has_align_big, has_new_high, has_tv_3x, has_pos_95])
    
    # ---------- V5: TV-P 페어 (거래대금+종가위치 함께만 인정) ----------
    has_tv_pos_pair = has_tv_2x and has_pos_85
    v5 = sum([has_align_big, has_new_high, has_tv_pos_pair])
    
    return {'gap': gap, 'V1': v1, 'V2': v2, 'V3': v3, 'V4': v4, 'V5': v5}


print('[2/3] 점수 계산...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = multi_score(arr, row_pos)
        if r is None: continue
        records.append(r)
print(f'  수집: {len(records):,}건, {time.time()-t0:.1f}초')

# numpy 변환
n = len(records)
v_arr = {k: np.array([r[k] for r in records], dtype=np.int8) for k in ['V1','V2','V3','V4','V5']}
gaps = np.array([r['gap'] for r in records], dtype=np.float64)

# -----------------------------------------------------------------------------
# 3. 변형별 점수 분포 + realized
# -----------------------------------------------------------------------------
def show_variant(name, scores, max_score):
    print()
    print(f'━━━━━ {name} (0~{max_score}) ━━━━━')
    print(f'  {"점수":<6} {"N":>8} {"비율":>7} {"Mean%":>9} {"Win%":>6} {"Real%":>9} {"증감":>8}')
    prev = None
    inversions = 0
    for s in range(max_score + 1):
        mask = scores == s
        nN = mask.sum()
        if nN < 5:
            continue
        g = gaps[mask]
        mean = g.mean()
        win = (g > 0).mean() * 100
        real = mean - ROUND_TRIP_COST_PCT
        delta = (real - prev) if prev is not None else None
        mark = ''
        if delta is not None and delta < -0.1:
            inversions += 1
            mark = ' ← 역전'
        print(f'  {s:<6} {nN:>8,} {nN/n*100:>6.2f}% {mean:>+8.3f}% '
              f'{win:>5.1f}% {real:>+8.3f}% '
              f'{(f"{delta:>+7.3f}%" if delta is not None else "  -"):>8}{mark}')
        prev = real
    print(f'  → 역전(Δ<-0.1%) 횟수: {inversions}')

print()
print('=' * 80)
print('[3/3] 카운트 기반 변형별 결과')
print('=' * 80)
show_variant('V1 최소 4조건', v_arr['V1'], 4)
show_variant('V2 모순배제 5조건', v_arr['V2'], 5)
show_variant('V3 가중 (신고가2점)', v_arr['V3'], 5)
show_variant('V4 스트릭트 4조건', v_arr['V4'], 4)
show_variant('V5 TV-P페어 3조건', v_arr['V5'], 3)


# -----------------------------------------------------------------------------
# 4. 변형 간 비교 — 컷오프 ≥ MAX 적용 시
# -----------------------------------------------------------------------------
print()
print('=' * 80)
print('변형별 최고점 (≥MAX) 컷오프 비교')
print('=' * 80)
print(f'{"변형":<25} {"N":>8} {"비율":>7} {"Mean%":>9} {"Win%":>6} {"Real%":>9} {"Cons%":>9}')
print('-' * 80)

variants_max = [
    ('V1 ≥4 (전조건)', v_arr['V1'], 4),
    ('V2 ≥4 (모순배제)', v_arr['V2'], 4),
    ('V2 ≥5 (전조건)', v_arr['V2'], 5),
    ('V3 ≥4 (가중)',  v_arr['V3'], 4),
    ('V3 ≥5 (가중 전조건)', v_arr['V3'], 5),
    ('V4 ≥3 (스트릭트)', v_arr['V4'], 3),
    ('V4 ≥4 (전조건)', v_arr['V4'], 4),
    ('V5 ≥2 (TV-P)',   v_arr['V5'], 2),
    ('V5 ≥3 (전조건)', v_arr['V5'], 3),
]
for name, sc, cut in variants_max:
    mask = sc >= cut
    nN = mask.sum()
    if nN < 5: continue
    g = gaps[mask]
    mean = g.mean()
    win = (g > 0).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    print(f'{name:<25} {nN:>8,} {nN/n*100:>6.2f}% {mean:>+8.3f}% '
          f'{win:>5.1f}% {real:>+8.3f}% {cons:>+8.3f}%')

# -----------------------------------------------------------------------------
# 5. 변형별 단조 증가성 + N 균형 종합 평가
# -----------------------------------------------------------------------------
print()
print('=' * 80)
print('종합 평가 (단조성 + 컷오프 N + realized)')
print('=' * 80)

def evaluate_variant(scores, max_score, name):
    inv_count = 0
    reals = []
    for s in range(max_score + 1):
        mask = scores == s
        if mask.sum() < 5: continue
        reals.append(gaps[mask].mean() - ROUND_TRIP_COST_PCT)
    for i in range(1, len(reals)):
        if reals[i] - reals[i-1] < -0.1:
            inv_count += 1
    # 최고점 그룹
    top_mask = scores == max_score
    top_n = top_mask.sum()
    top_real = gaps[top_mask].mean() - ROUND_TRIP_COST_PCT if top_n >= 5 else None
    return {
        'name': name, 'inversions': inv_count,
        'monotone_score': len(reals) - inv_count,  # 더 높으면 좋음
        'top_n': top_n, 'top_real': top_real,
    }

evs = [
    evaluate_variant(v_arr['V1'], 4, 'V1 최소 4조건'),
    evaluate_variant(v_arr['V2'], 5, 'V2 모순배제 5조건'),
    evaluate_variant(v_arr['V3'], 5, 'V3 가중'),
    evaluate_variant(v_arr['V4'], 4, 'V4 스트릭트'),
    evaluate_variant(v_arr['V5'], 3, 'V5 TV-P페어'),
]
print(f'{"변형":<22} {"역전":>5} {"단조점":>7} {"최고점N":>10} {"최고realized":>14}')
print('-' * 80)
for e in evs:
    tr = f'{e["top_real"]:+.3f}%' if e['top_real'] is not None else 'N/A'
    print(f'{e["name"]:<22} {e["inversions"]:>5} {e["monotone_score"]:>7} '
          f'{e["top_n"]:>10,} {tr:>14}')

print()
print('완료.')
