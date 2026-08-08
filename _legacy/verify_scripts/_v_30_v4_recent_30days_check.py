"""_v_30_v4_recent_30days_check.py — V4 최근 1개월 실전 검증

목적:
  최근 30 영업일 (DB 기준) 의 score==4/3 종목을 추출하여
  실제 T+1일 갭업률 측정. 백테스트(_v_27) 추정값과 비교.

판정 기준:
  ① 최근 30일 score==4 평균 gap >= +1.0% (백테스트 +3.5% 대비 보수적)
  ② 갭5%+ 비율 >= 10% (백테스트 19.96% 대비 보수적)
  ③ score==4 발생 일수 >= 5일 (시그널 정상 작동)
  ④ 종목별 사례 검증
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict, Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46

# 종목명 매핑용 (있으면 사용)
NAME_DB_PATHS = [
    r'D:\StockAnalyst\trading_system.db',
    r'D:\StockAnalyst\ohlcv_long.db',
]

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/4] 거래일 + 최근 30일 결정...')
all_dates = [r[0] for r in cur.execute(
    "SELECT DISTINCT date FROM daily_ohlcv_long "
    "WHERE date >= '20140101' ORDER BY date"
).fetchall()]
date_index = {d: i for i, d in enumerate(all_dates)}

# 최근 30 영업일 (마지막 일자에서 거꾸로 30일)
last_date = all_dates[-1]
recent_dates = all_dates[-31:-1]  # T+1 데이터 필요해서 마지막은 제외
print(f'  DB 마지막 날짜: {last_date}')
print(f'  검증 기간: {recent_dates[0]} ~ {recent_dates[-1]} ({len(recent_dates)}일)')
recent_idx_set = {date_index[d] for d in recent_dates}

print('[2/4] OHLCV 로드...')
t0 = time.time()
by_code_raw = defaultdict(list)
for code, date, o, h, lo, cl, v in cur.execute(
    "SELECT code, date, open, high, low, close, volume FROM daily_ohlcv_long "
    "WHERE date >= '20251101' AND substr(code, -1) = '0' ORDER BY code, date"
):
    idx = date_index.get(date)
    if idx is None: continue
    by_code_raw[code].append((idx, o, h, lo, cl, v))

# 종목명 시도 — 있는 DB만
code_to_name = {}
for db in NAME_DB_PATHS:
    try:
        c2 = sqlite3.connect(db, timeout=5)
        for tbl in ['stock_master', 'stock_info', 'company_info', 'tickers']:
            try:
                rows = c2.execute(f"SELECT code, name FROM {tbl}").fetchall()
                for code, name in rows:
                    if code and name and code not in code_to_name:
                        code_to_name[code] = name
                if rows:
                    break
            except sqlite3.OperationalError:
                continue
        c2.close()
        if code_to_name:
            print(f'  종목명 매핑 로드: {db}, {len(code_to_name):,}건')
            break
    except Exception:
        continue
if not code_to_name:
    print('  종목명 매핑 없음 (코드만 표시)')

# 6개월치만 numpy (속도)
by_code = {}
for code, rows in by_code_raw.items():
    if len(rows) < 61: continue
    by_code[code] = np.array(rows, dtype=np.float64)
del by_code_raw
print(f'  로드: {len(by_code):,}종목, {time.time()-t0:.1f}초')
conn.close()


# -----------------------------------------------------------------------------
# V4 점수 계산 (_v_26 동일)
# -----------------------------------------------------------------------------
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
    return {
        'gap': gap, 'score': score, 'close': close_t, 'vol': vol_t,
        'today_tv_won': today_tv,
        'tv_ratio': today_tv / avg20 if avg20 > 0 else 0,
        'close_pos': (close_t - low_t) / rng if rng > 0 else 0,
    }


print('[3/4] 최근 30일 score 계산...')
t0 = time.time()
records_4 = []
records_3 = []
records_2 = []
date_score_count = defaultdict(lambda: Counter())  # date -> Counter

for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, date_idx in enumerate(dates_col):
        if date_idx not in recent_idx_set: continue
        r = v4_score(arr, row_pos)
        if r is None: continue
        s = r['score']
        date_str = all_dates[date_idx]
        date_score_count[date_str][s] += 1
        rec = {
            'code': code, 'date': date_str, 'score': s,
            'gap': r['gap'], 'close': r['close'],
            'tv_won_eok': r['today_tv_won'] / 1e8,  # 억원
            'tv_ratio': r['tv_ratio'], 'close_pos': r['close_pos'],
        }
        if s == 4:
            records_4.append(rec)
        elif s == 3:
            records_3.append(rec)
        elif s == 2:
            records_2.append(rec)
print(f'  완료: score==4 {len(records_4)}건 / score==3 {len(records_3)}건 / score==2 {len(records_2)}건, {time.time()-t0:.1f}초')


# -----------------------------------------------------------------------------
# 4. 결과 요약
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('[4/4] 최근 30일 V4 시그널 발생 분석')
print('=' * 100)

def stats(recs, label):
    if not recs:
        print(f'\n{label}: 0건 — 시그널 발생 없음')
        return None
    gaps = np.array([r['gap'] for r in recs])
    n = len(recs)
    mean = gaps.mean()
    median = np.median(gaps)
    win = (gaps > 0).mean() * 100
    win_strong = (gaps > 1).mean() * 100
    gu5 = (gaps >= 5).mean() * 100
    real = mean - ROUND_TRIP_COST_PCT
    cons = mean - 0.76
    print(f'\n{label}:')
    print(f'  N={n}, 발생 일수={len({r["date"] for r in recs})}일')
    print(f'  Mean: {mean:+.3f}% | Median: {median:+.3f}%')
    print(f'  승률 (gap > 0): {win:.1f}% | 강승 (gap > 1%): {win_strong:.1f}% | 갭 5%↑: {gu5:.1f}%')
    print(f'  realized: {real:+.3f}% | conservative: {cons:+.3f}%')
    return {'n': n, 'mean': mean, 'real': real, 'cons': cons, 'win': win, 'gu5': gu5}

s4 = stats(records_4, '★ score == 4 (Mode A 매수 대상)')
s3 = stats(records_3, '○ score == 3 (Mode B 보충매수 후보)')
s2 = stats(records_2, '· score == 2 (참조)')

# 일별 score==4 분포
print()
print('-' * 100)
print('일별 score==4 발생 분포:')
day4 = defaultdict(int)
for r in records_4:
    day4[r['date']] += 1
for d in sorted(day4.keys()):
    bar = '█' * day4[d]
    print(f'  {d}: {day4[d]:>2}건 {bar}')

# Mode A 자본 시뮬레이션 (간단)
print()
print('-' * 100)
print('Mode A 시뮬레이션 (1억 자본, 운용 30%, 종목당 5%):')
WORKING = 30_000_000
PER_MAX = 1_500_000
SLIP = 0.5  # 평균 슬리피지 가정
capital = 100_000_000
total_pnl = 0
for d in sorted(day4.keys()):
    day_recs = [r for r in records_4 if r['date'] == d]
    n = min(len(day_recs), 30)
    slot = min(WORKING / n, PER_MAX) if n > 0 else 0
    day_pnl = 0
    for r in day_recs[:n]:
        pnl = slot * (r['gap'] - SLIP) / 100
        day_pnl += pnl
    total_pnl += day_pnl
    print(f'  {d}: {n}종목, day_pnl {day_pnl:>+12,.0f}원')
final_cap = capital + total_pnl
ret = (final_cap / capital - 1) * 100
print(f'  → 30일 누적 수익: {total_pnl:+,.0f}원 ({ret:+.2f}%)')
print(f'  연환산 (250영업일 가정): {ret * 250 / len(day4):+.2f}%')


# -----------------------------------------------------------------------------
# 5. 종목별 사례 검증 (score==4 상위 10건)
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('score==4 종목 사례 (gap 정렬, 상위 10건):')
print('=' * 100)
print(f'{"날짜":<10} {"코드":<8} {"종목명":<16} {"종가":>9} {"거래대금억":>10} {"TV비율":>8} {"종가위치":>8} {"T+1 gap":>10}')
print('-' * 100)
sorted_by_gap = sorted(records_4, key=lambda r: -r['gap'])[:10]
for r in sorted_by_gap:
    name = code_to_name.get(r['code'], '-')[:14]
    print(f'{r["date"]:<10} {r["code"]:<8} {name:<16} {r["close"]:>9,.0f} '
          f'{r["tv_won_eok"]:>9.1f}억 {r["tv_ratio"]:>6.2f}x '
          f'{r["close_pos"]:>7.2%} {r["gap"]:>+9.2f}%')

print()
print('score==4 종목 사례 (gap 정렬, 하위 5건):')
print('-' * 100)
sorted_by_gap_low = sorted(records_4, key=lambda r: r['gap'])[:5]
for r in sorted_by_gap_low:
    name = code_to_name.get(r['code'], '-')[:14]
    print(f'{r["date"]:<10} {r["code"]:<8} {name:<16} {r["close"]:>9,.0f} '
          f'{r["tv_won_eok"]:>9.1f}억 {r["tv_ratio"]:>6.2f}x '
          f'{r["close_pos"]:>7.2%} {r["gap"]:>+9.2f}%')

# -----------------------------------------------------------------------------
# 6. 백테스트 vs 실전 비교
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('백테스트 (_v_27 Mode A, 13년) vs 최근 30일 비교')
print('=' * 100)
print(f'{"지표":<25} {"백테스트":>15} {"최근 30일":>15} {"차이":>15}')
print('-' * 100)
if s4:
    bt_real = 3.044
    bt_win = 63.1
    bt_gu5 = 19.96
    bt_n_per_year = 616 / (2956/252)  # _v_26 N=616, 2956샘플일
    bt_n_30d = bt_n_per_year * 30 / 252
    
    print(f'{"score==4 평균 gap":<25} {bt_real + 0.46:>14.3f}% {s4["mean"]:>14.3f}% {s4["mean"] - (bt_real+0.46):>+14.3f}%')
    print(f'{"realized (수수료차감)":<25} {bt_real:>14.3f}% {s4["real"]:>14.3f}% {s4["real"] - bt_real:>+14.3f}%')
    print(f'{"승률 (gap > 0)":<25} {bt_win:>14.1f}% {s4["win"]:>14.1f}% {s4["win"] - bt_win:>+14.1f}%')
    print(f'{"갭 5%↑ 비율":<25} {bt_gu5:>14.2f}% {s4["gu5"]:>14.2f}% {s4["gu5"] - bt_gu5:>+14.2f}%')
    print(f'{"30일 N (예상)":<25} {bt_n_30d:>15.1f} {s4["n"]:>15} {s4["n"] - bt_n_30d:>+15.1f}')

# -----------------------------------------------------------------------------
# 7. 판정
# -----------------------------------------------------------------------------
print()
print('=' * 100)
print('실전 검증 판정')
print('=' * 100)
if s4:
    crit1 = s4['mean'] >= 1.0
    crit2 = s4['gu5'] >= 10.0
    crit3 = len({r['date'] for r in records_4}) >= 5
    print(f'  ① 평균 gap >= +1.0%: {"✅" if crit1 else "❌"} ({s4["mean"]:+.3f}%)')
    print(f'  ② 갭 5%↑ >= 10%:    {"✅" if crit2 else "❌"} ({s4["gu5"]:.1f}%)')
    print(f'  ③ 발생 일수 >= 5일:  {"✅" if crit3 else "❌"} ({len({r["date"] for r in records_4})}일)')
    print()
    if crit1 and crit2 and crit3:
        print('✅ 실전 검증 통과 — V4 시그널 최근 시장에서도 정상 작동')
    else:
        print('⚠ 일부 기준 미달 — 추가 분석 필요')
else:
    print('  ❌ score==4 발생 0건 — 시그널 발생 임계점 너무 높음 또는 시장 비활성')

print()
print('완료.')
