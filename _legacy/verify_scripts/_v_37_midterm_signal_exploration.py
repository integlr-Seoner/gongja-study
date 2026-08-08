"""_v_37_midterm_signal_exploration.py — 중기 보유(T+20)용 시그널 발굴

배경:
  V4 (score==4) 는 T+1 전용 (_v_32). T+20 까지 보유하면 realized -0.391%.
  중기 보유용 완전히 다른 시그널이 필요.

가설 6개:
  G1 깊은 정배열 (MA5>10>20>60>120)
  G2 변동성 압축 후 60일 신고가 (ATR 20일 하락 → 돌파)
  G3 상대강도 (종목 20d > KOSPI 20d + 5%p, KOSPI 20d > 0)
  G4 거래량 꾸준한 증가 (20일/120일 >= 1.3)
  G5 MA20 눌림목 반등
  G6 V4=4 AND 장기 정배열 교집합

측정:
  T+20 close 수익률 (T+5 도 참조)
  각 가설 vs 베이스라인(전체) 비교

판정 기준:
  T+20 realized 양수 + 베이스라인 대비 +1.5%p+ 우위 = 유효 시그널
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

print('[1/5] 거래일 + 샘플...')
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
print(f'  샘플 {len(samples)}일')

print('[2/5] KOSPI 지수 로드 (상대강도용)...')
kospi_rows = cur.execute(
    "SELECT date, close FROM daily_index_long "
    "WHERE symbol='KOSPI' AND date >= '20140101' ORDER BY date"
).fetchall()
kospi_close_by_date = {d: c for d, c in kospi_rows}
print(f'  KOSPI {len(kospi_close_by_date):,}일')

print('[3/5] OHLCV 로드 (120+ 필요, T+20 보장 위해 80+1 일 이상)...')
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
    # G1 MA120 필요 + T+20 여유 → 141일 이상
    if len(rows) < 141: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


# -----------------------------------------------------------------------------
# 6가지 가설 + T+5/T+20 수익률 측정
# -----------------------------------------------------------------------------
def measure(arr, t_pos, date_str):
    """6가지 가설별 bool + T+5/T+20 수익률"""
    # 데이터 충분성
    if t_pos < 120 or t_pos + 20 >= len(arr): return None
    
    # 연속 20일 확인 (T+1~T+20)
    base_idx = int(arr[t_pos, 0])
    for k in range(1, 21):
        if int(arr[t_pos+k, 0]) != base_idx + k:
            return None
    
    o, h, lo, c, v = arr[:,1], arr[:,2], arr[:,3], arr[:,4], arr[:,5]
    close_t = c[t_pos]; vol_t = v[t_pos]
    if close_t < MIN_PRICE or vol_t < MIN_VOL: return None
    
    close_t5 = c[t_pos+5]; close_t20 = c[t_pos+20]
    if close_t5 <= 0 or close_t20 <= 0: return None
    
    ret_5d = (close_t5 / close_t - 1) * 100
    ret_20d = (close_t20 / close_t - 1) * 100
    
    # 이동평균 5 / 10 / 20 / 60 / 120
    ma5 = c[t_pos-4:t_pos+1].mean()
    ma10 = c[t_pos-9:t_pos+1].mean()
    ma20 = c[t_pos-19:t_pos+1].mean()
    ma60 = c[t_pos-59:t_pos+1].mean()
    ma120 = c[t_pos-119:t_pos+1].mean()
    
    # G1 — 깊은 정배열
    g1 = (ma5 > ma10 > ma20 > ma60 > ma120)
    
    # G2 — 변동성 압축 후 60일 신고가
    # ATR 20일 (True Range 평균) 이 최근 60일 중 하위 30% 이내 + 60일 신고가
    trs = np.zeros(60)
    for k in range(60):
        idx = t_pos - 59 + k
        if idx < 1: continue
        h_k = h[idx]; l_k = lo[idx]; c_prev = c[idx-1]
        trs[k] = max(h_k - l_k, abs(h_k - c_prev), abs(l_k - c_prev))
    atr_20_recent = trs[-20:].mean()
    atr_60_sorted = np.sort(trs)
    atr_30pct = atr_60_sorted[int(60 * 0.3)]
    is_compressed = atr_20_recent <= atr_30pct
    is_new_high = h[t_pos] > h[t_pos-60:t_pos].max()
    g2 = is_compressed and is_new_high
    
    # G3 — 상대강도
    kospi_now = kospi_close_by_date.get(date_str)
    kospi_20_dates_ago = all_dates[t_pos - 20] if t_pos - 20 >= 0 else None
    kospi_20d_close = kospi_close_by_date.get(kospi_20_dates_ago) if kospi_20_dates_ago else None
    g3 = False
    if kospi_now and kospi_20d_close and kospi_20d_close > 0:
        kospi_ret_20d = (kospi_now / kospi_20d_close - 1) * 100
        stock_ret_20d = (close_t / c[t_pos-20] - 1) * 100 if c[t_pos-20] > 0 else 0
        g3 = (kospi_ret_20d > 0) and (stock_ret_20d > kospi_ret_20d + 5)
    
    # G4 — 거래량 꾸준한 증가
    vol_20d_avg = v[t_pos-19:t_pos+1].mean()
    vol_120d_avg = v[t_pos-119:t_pos+1].mean()
    g4 = (vol_120d_avg > 0) and (vol_20d_avg / vol_120d_avg >= 1.3)
    
    # G5 — MA20 눌림목 반등
    # 최근 5일 내 close 가 MA20 아래로 내려갔다가 지금 MA20 위에 있음
    close_5d = c[t_pos-4:t_pos+1]
    ma20_5d = np.array([c[t_pos-4+k-19:t_pos-4+k+1].mean() for k in range(5)])
    went_below = np.any(close_5d[:-1] < ma20_5d[:-1])  # 최근 4일 내 이탈
    now_above = close_t > ma20  # 오늘 복귀
    g5 = went_below and now_above
    
    # G6 — V4=4 AND 장기 정배열 교집합
    # V4 재계산
    body = close_t - o[t_pos]; rng = h[t_pos] - lo[t_pos]
    cond1 = (ma5 > ma10 > ma20) and rng > 0 and body > 0 and (body / rng > 0.6)
    cond2 = h[t_pos] > h[t_pos-60:t_pos].max()
    tv_arr = c[t_pos-20:t_pos] * v[t_pos-20:t_pos]
    avg20_tv = tv_arr.mean()
    today_tv = close_t * vol_t
    cond3 = (avg20_tv > 0) and (today_tv / avg20_tv >= 3.0)
    cond4 = (rng > 0) and ((close_t - lo[t_pos]) / rng >= 0.95)
    v4_score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    g6 = (v4_score == 4) and g1  # V4 만점 + 장기 정배열
    
    return {
        'ret_5d': ret_5d, 'ret_20d': ret_20d,
        'g1': g1, 'g2': g2, 'g3': g3, 'g4': g4, 'g5': g5, 'g6': g6,
        'v4_score': v4_score,
    }


print('[4/5] 측정 (T+5/T+20 + 6가지 가설)...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        date_str = all_dates[date_idx]
        r = measure(arr, row_pos, date_str)
        if r is None: continue
        records.append(r)
print(f'  완료: {len(records):,}건, {time.time()-t0:.1f}초')


# -----------------------------------------------------------------------------
# 5. 가설별 결과
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('[5/5] 6가지 가설별 T+5 / T+20 수익률 결과')
print('=' * 110)

# 베이스라인
ret5_all = np.array([r['ret_5d'] for r in records])
ret20_all = np.array([r['ret_20d'] for r in records])

print(f'\n--- 베이스라인 (전체 자격 통과) ---')
print(f'  N={len(records):,}')
print(f'  T+5:  mean {ret5_all.mean():+.3f}% / std {ret5_all.std():.3f}% / '
      f'승률 {(ret5_all>0).mean()*100:.1f}%')
print(f'  T+20: mean {ret20_all.mean():+.3f}% / std {ret20_all.std():.3f}% / '
      f'승률 {(ret20_all>0).mean()*100:.1f}%')

print()
print(f'{"가설":<50} {"N":>8} {"T+5":>10} {"T+20":>10} {"T+20 승률":>10} {"T+20 real":>11}')
print('-' * 110)

GATES = [
    ('G1 깊은 정배열 (MA5>10>20>60>120)', 'g1'),
    ('G2 변동성 압축 후 60일 신고가', 'g2'),
    ('G3 상대강도 (stock 20d > KOSPI + 5%p)', 'g3'),
    ('G4 거래량 꾸준한 증가 (20일/120일 >= 1.3)', 'g4'),
    ('G5 MA20 눌림목 반등', 'g5'),
    ('G6 V4=4 AND G1 교집합', 'g6'),
]

results_summary = {}
for name, key in GATES:
    sub = [r for r in records if r[key]]
    if len(sub) < 30:
        print(f'{name:<50} {len(sub):>8} {"(N부족)":>10}')
        continue
    r5 = np.array([r['ret_5d'] for r in sub])
    r20 = np.array([r['ret_20d'] for r in sub])
    real_20 = r20.mean() - ROUND_TRIP_COST_PCT
    win_20 = (r20 > 0).mean() * 100
    print(f'{name:<50} {len(sub):>8,} '
          f'{r5.mean():>+9.3f}% {r20.mean():>+9.3f}% '
          f'{win_20:>9.1f}% {real_20:>+10.3f}%')
    results_summary[key] = {
        'name': name, 'n': len(sub),
        'ret5_mean': r5.mean(), 'ret20_mean': r20.mean(),
        'ret20_win': win_20, 'ret20_real': real_20,
        'vs_baseline_20': r20.mean() - ret20_all.mean(),
    }

# -----------------------------------------------------------------------------
# 6. 베이스라인 대비 우위 분석
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('베이스라인(T+20 {:+.3f}%) 대비 우위'.format(ret20_all.mean()))
print('=' * 110)
print(f'{"가설":<50} {"T+20":>10} {"차이":>10} {"판정":<20}')
print('-' * 110)
sorted_gates = sorted(results_summary.items(), 
                     key=lambda x: -x[1]['vs_baseline_20'])
for key, s in sorted_gates:
    diff = s['vs_baseline_20']
    if s['ret20_real'] > 0 and diff >= 1.5:
        verdict = '✅ 유효 (강)'
    elif s['ret20_real'] > 0 and diff >= 0.5:
        verdict = '⚠ 약한 우위'
    elif diff > 0:
        verdict = '참조'
    else:
        verdict = '❌ 열위'
    print(f'{s["name"]:<50} {s["ret20_mean"]:>+9.3f}% {diff:>+9.3f}%p {verdict:<20}')


# -----------------------------------------------------------------------------
# 7. 유효 시그널 교집합 분석 (다중 가설 동시 충족)
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('다중 가설 교집합 (합집합 = AND)')
print('=' * 110)

# 각 레코드별 충족 가설 개수
for r in records:
    r['gate_count'] = sum([r['g1'], r['g2'], r['g3'], r['g4'], r['g5']])

print(f'{"충족 가설 수":<15} {"N":>8} {"T+5":>10} {"T+20":>10} {"T+20 win":>10} {"T+20 real":>11}')
print('-' * 110)
for k in range(6):
    sub = [r for r in records if r['gate_count'] == k]
    if len(sub) < 30:
        print(f'{k}개 충족{"":<9} {len(sub):>8} {"(N<30)":>10}')
        continue
    r5 = np.array([r['ret_5d'] for r in sub])
    r20 = np.array([r['ret_20d'] for r in sub])
    win = (r20 > 0).mean() * 100
    real = r20.mean() - ROUND_TRIP_COST_PCT
    print(f'{k}개 충족{"":<9} {len(sub):>8,} '
          f'{r5.mean():>+9.3f}% {r20.mean():>+9.3f}% '
          f'{win:>9.1f}% {real:>+10.3f}%')

# -----------------------------------------------------------------------------
# 8. 추천 시그널 (최강 1~2개 선별)
# -----------------------------------------------------------------------------
print()
print('=' * 110)
print('추천 중기 시그널 (realized 양수 + 단조성 가장 명확)')
print('=' * 110)

# 최상위 가설 2개 선별
best_gates = sorted(
    [(k, s) for k, s in results_summary.items() if s['ret20_real'] > 0],
    key=lambda x: -x[1]['ret20_real']
)[:2]

if best_gates:
    print('\n최상위 가설:')
    for i, (key, s) in enumerate(best_gates, 1):
        sub = [r for r in records if r[key]]
        r20 = np.array([r['ret_20d'] for r in sub])
        p10 = np.percentile(r20, 10)
        p90 = np.percentile(r20, 90)
        print(f'\n  {i}. {s["name"]}')
        print(f'     N={s["n"]:,}, T+20 realized {s["ret20_real"]:+.3f}%, 승률 {s["ret20_win"]:.1f}%')
        print(f'     베이스라인 대비 +{s["vs_baseline_20"]:.3f}%p 우위')
        print(f'     분포: p10 {p10:+.2f}% / 중간 {np.median(r20):+.2f}% / p90 {p90:+.2f}%')

print()
print('완료.')
