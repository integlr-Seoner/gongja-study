"""_v_33_v4_sector_analysis.py — V4 시그널 섹터별 + 가격대별 교차 분석

배경:
  실섹터 매핑이 종목 1,472개 중 157개만 가능 (OTHER 1,315개).
  섹터 분석은 매핑 가능한 종목만, 가격대/거래대금 분석은 전 종목.

분석:
  ① 실섹터 매핑된 종목의 V4 score==4 분포 (어느 섹터가 가장 잘 작동하는가)
  ② 가격대별 V4 score==4 분포 (저가/중가/고가)
  ③ 거래대금 규모별 V4 score==4 (소형/중형/대형)
  ④ 시기별 + 섹터별 변화 (P3 강세 섹터 식별)
"""
import sqlite3, json
import numpy as np
import time
from collections import defaultdict, Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'
SECTOR_MAP = r'D:\StockAnalyst\code_sector_map.json'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

with open(SECTOR_MAP, encoding='utf-8') as f:
    code_to_sector = json.load(f)
print(f'섹터 매핑 로드: {len(code_to_sector):,}건')
real_codes = {c for c, s in code_to_sector.items() if s != 'OTHER'}
print(f'실섹터 매핑 종목: {len(real_codes)}개')

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('\n[1/4] 거래일 + 샘플...')
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
print(f'  거래일 {len(all_dates):,}, 샘플 {len(samples)}')

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
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


def measure(arr, t_pos):
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
    return {
        'gap': gap, 'score': score,
        'close': close_t, 'today_tv_won': today_tv,
        'date': all_dates[int(arr[t_pos, 0])],
    }


print('[3/4] V4 점수 + 메타 수집 (score>=2 만)...')
t0 = time.time()
records = []
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in sample_idx_set: continue
        r = measure(arr, row_pos)
        if r is None or r['score'] < 2: continue  # score 0/1 제외 (메모리 절약)
        r['code'] = code
        r['sector'] = code_to_sector.get(code, 'OTHER')
        records.append(r)
print(f'  수집: {len(records):,}건, {time.time()-t0:.1f}초')

# -----------------------------------------------------------------------------
# 분석 1: 실섹터 매핑 종목의 V4 score==4 분포
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('[4/4] 분석')
print('=' * 100)

s4_real = [r for r in records if r['score'] == 4 and r['sector'] != 'OTHER']
print(f'\n--- ① score==4 + 실섹터 매핑된 발생 분포 (총 {len(s4_real)}건) ---')
sec_dist = Counter(r['sector'] for r in s4_real)
print(f'{"섹터":<20} {"N":>5} {"평균gap":>9} {"승률":>8} {"갭5%↑":>8} {"realized":>10}')
print('-' * 100)
for sec, n in sec_dist.most_common(20):
    if n < 3: continue  # N<3 노이즈
    gaps = np.array([r['gap'] for r in s4_real if r['sector'] == sec])
    print(f'{sec:<20} {n:>5} {gaps.mean():>+8.3f}% '
          f'{(gaps>0).mean()*100:>7.1f}% {(gaps>=5).mean()*100:>7.1f}% '
          f'{gaps.mean()-ROUND_TRIP_COST_PCT:>+9.3f}%')

# 비교: OTHER 그룹
s4_other = [r for r in records if r['score'] == 4 and r['sector'] == 'OTHER']
if s4_other:
    gaps_o = np.array([r['gap'] for r in s4_other])
    print(f'\n  OTHER (실섹터 미매핑, 참조): N={len(s4_other)}, '
          f'mean={gaps_o.mean():+.3f}%, win={(gaps_o>0).mean()*100:.1f}%')

# -----------------------------------------------------------------------------
# 분석 2: 가격대별 V4 score==4
# -----------------------------------------------------------------------------
print()
print('--- ② 가격대별 score==4 분포 ---')
price_bins = [(0, 2000, '저가 (~2k)'),
              (2000, 5000, '저-중가 (2~5k)'),
              (5000, 10000, '중가 (5~10k)'),
              (10000, 30000, '중-고가 (10~30k)'),
              (30000, 100000, '고가 (30~100k)'),
              (100000, 999999999, '초고가 (100k+)')]
print(f'{"가격대":<22} {"N":>6} {"mean":>9} {"승률":>8} {"갭5%↑":>8} {"realized":>10}')
print('-' * 100)
s4_all = [r for r in records if r['score'] == 4]
for lo_p, hi_p, label in price_bins:
    sub = [r for r in s4_all if lo_p <= r['close'] < hi_p]
    if len(sub) < 5: continue
    gaps = np.array([r['gap'] for r in sub])
    print(f'{label:<22} {len(sub):>6} {gaps.mean():>+8.3f}% '
          f'{(gaps>0).mean()*100:>7.1f}% {(gaps>=5).mean()*100:>7.1f}% '
          f'{gaps.mean()-ROUND_TRIP_COST_PCT:>+9.3f}%')


# -----------------------------------------------------------------------------
# 분석 3: 거래대금 규모별 V4 score==4
# -----------------------------------------------------------------------------
print()
print('--- ③ 거래대금 규모별 score==4 분포 ---')
tv_bins = [(0, 50, '소형 (~50억)'),
           (50, 200, '중형 (50~200억)'),
           (200, 1000, '대형 (200~1000억)'),
           (1000, 5000, '초대형 (1000~5000억)'),
           (5000, 999999999, '메가 (5000억+)')]
print(f'{"거래대금":<22} {"N":>6} {"mean":>9} {"승률":>8} {"갭5%↑":>8} {"realized":>10}')
print('-' * 100)
for lo_t, hi_t, label in tv_bins:
    sub = [r for r in s4_all
           if lo_t <= r['today_tv_won']/1e8 < hi_t]
    if len(sub) < 5: continue
    gaps = np.array([r['gap'] for r in sub])
    print(f'{label:<22} {len(sub):>6} {gaps.mean():>+8.3f}% '
          f'{(gaps>0).mean()*100:>7.1f}% {(gaps>=5).mean()*100:>7.1f}% '
          f'{gaps.mean()-ROUND_TRIP_COST_PCT:>+9.3f}%')

# -----------------------------------------------------------------------------
# 분석 4: 시기별 + 섹터별 (P3=2023-2026 강세 섹터)
# -----------------------------------------------------------------------------
print()
print('--- ④ P3 (2023~2026) 강세 섹터 식별 ---')
PERIODS = {
    'P1_14_18': ('20140101', '20181231'),
    'P2_19_22': ('20190101', '20221231'),
    'P3_23_26': ('20230101', '20261231'),
}
def period_of(d):
    for n, (s, e) in PERIODS.items():
        if s <= d <= e: return n
    return None

# 섹터 × 시기별 매트릭스 (실섹터만)
print(f'{"섹터":<20}', end='')
for p in PERIODS: print(f' {p:>11}', end='')
print(f' {"전체avg":>9}')
print('-' * 100)
sec_period = defaultdict(lambda: defaultdict(list))
for r in s4_real:
    p = period_of(r['date'])
    if p: sec_period[r['sector']][p].append(r['gap'])

for sec, n_total in sec_dist.most_common(20):
    if n_total < 5: continue
    line = f'{sec:<20}'
    all_gaps = []
    for p in PERIODS:
        gaps = sec_period[sec][p]
        if gaps:
            mean = np.mean(gaps)
            line += f' {len(gaps):>3}|{mean:>+5.1f}%'
            all_gaps += gaps
        else:
            line += f' {"-":>10}'
    if all_gaps:
        line += f' {np.mean(all_gaps):>+8.3f}%'
    print(line)


# -----------------------------------------------------------------------------
# 분석 5: 종합 권고
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('종합 권고')
print('=' * 100)

# 가격대 최적
best_price = None; best_real_p = -999
for lo_p, hi_p, label in price_bins:
    sub = [r for r in s4_all if lo_p <= r['close'] < hi_p]
    if len(sub) < 10: continue
    real = np.mean([r['gap'] for r in sub]) - ROUND_TRIP_COST_PCT
    if real > best_real_p:
        best_real_p = real; best_price = label

# 거래대금 최적
best_tv = None; best_real_t = -999
for lo_t, hi_t, label in tv_bins:
    sub = [r for r in s4_all if lo_t <= r['today_tv_won']/1e8 < hi_t]
    if len(sub) < 10: continue
    real = np.mean([r['gap'] for r in sub]) - ROUND_TRIP_COST_PCT
    if real > best_real_t:
        best_real_t = real; best_tv = label

# 섹터 최적 (N>=5)
best_sec = None; best_real_s = -999
for sec, n in sec_dist.most_common():
    if n < 5: continue
    sub = [r for r in s4_real if r['sector'] == sec]
    real = np.mean([r['gap'] for r in sub]) - ROUND_TRIP_COST_PCT
    if real > best_real_s:
        best_real_s = real; best_sec = sec

print(f'  최적 가격대: {best_price} (realized {best_real_p:+.3f}%)')
print(f'  최적 거래대금: {best_tv} (realized {best_real_t:+.3f}%)')
print(f'  최강 섹터 (N>=5): {best_sec} (realized {best_real_s:+.3f}%)')

# OTHER 비율 경고
other_ratio = len(s4_other) / len(s4_all) * 100 if s4_all else 0
print(f'\n  ⚠ score==4 중 실섹터 미매핑(OTHER) 비율: {other_ratio:.1f}%')
if other_ratio > 80:
    print(f'    → 섹터 분석 신뢰도 제한적 (대부분 종목이 OTHER)')

print()
print('완료.')
