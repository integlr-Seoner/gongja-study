"""_v_47_v4_realistic_slippage.py — V4 실전 슬리피지 반영 시뮬레이션

배경:
  §33/§35 에서 ps=0.10 이 최적 파라미터로 확인.
  그러나 §35 롤링 윈도우는 슬리피지 미반영 → 실전 적용 전 실측 필수.

가설:
  ps 상향 = 종목당 주문 크기 증가 = 시장 충격 증가
  특히 저거래대금 종목에서 슬리피지 심각
  자본 규모 클수록 슬리피지 더 큼

슬리피지 모델:
  slip_spread (호가 스프레드, 매수+매도 합):
    close < 1000:   0.50%
    close < 5000:   0.20%
    close < 10000:  0.10%
    close >= 10000: 0.05%
  
  slip_impact (시장 충격, participation = order / daily_tv):
    > 5%:  1.00%
    > 2%:  0.50%
    > 1%:  0.30%
    > 0.5%: 0.15%
    else:  0.05%

판정:
  ps=0.10 이 ps=0.07 대비 실전 슬리피지 반영해도 우위면 → 권고 상향
  아니면 ps=0.07 유지
"""
import sqlite3
import numpy as np
import time
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46  # 기존: 세금+수수료 (슬리피지 제외)


conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('[1/3] OHLCV 로드 + 샘플일 V4 상세 수집...')
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


def v4_detail(arr, t_pos):
    """V4 score==4 시 상세 정보 반환 (slippage 계산용)"""
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
    today_tv = close_t * vol_t
    cond3 = tv_arr.mean() > 0 and (today_tv / tv_arr.mean() >= 3.0)
    cond4 = (rng > 0) and ((close_t - lo[t_pos]) / rng >= 0.95)
    score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    if score != 4: return None
    return {
        'gap': (open_t1 / close_t - 1) * 100,
        'close': close_t,
        'daily_tv': today_tv,   # 당일 거래대금 (원)
    }


print('\n[2/3] 월별 V4=4 상세 수집...')
t0 = time.time()
detail_by_month = defaultdict(list)
for code, arr in by_code.items():
    dates_col = arr[:,0].astype(int)
    for row_pos, d_idx in enumerate(dates_col):
        if d_idx not in sample_idx_set: continue
        d = v4_detail(arr, row_pos)
        if d is not None:
            detail_by_month[all_dates[d_idx]].append(d)
print(f'  총 {sum(len(v) for v in detail_by_month.values())}건, {time.time()-t0:.1f}초')


def slip_spread_pct(close):
    """호가 스프레드 슬리피지 % (매수+매도 합, 왕복)"""
    if close < 1000:   return 0.50
    elif close < 5000:  return 0.20
    elif close < 10000: return 0.10
    else:               return 0.05


def slip_impact_pct(order_krw, daily_tv_krw):
    """시장 충격 슬리피지 % (매수+매도 합, 왕복)"""
    if daily_tv_krw <= 0: return 0.05
    participation = order_krw / daily_tv_krw
    if participation > 0.05:  return 1.00
    elif participation > 0.02: return 0.50
    elif participation > 0.01: return 0.30
    elif participation > 0.005: return 0.15
    else: return 0.05


def monthly_return_with_slippage(details, capital_krw, working_ratio, per_stock, max_pos=30):
    """슬리피지 반영 월 수익률
    
    Args:
        details: 당월 V4=4 종목 리스트 [{gap, close, daily_tv}, ...]
        capital_krw: V4 자본 규모 (원)
        working_ratio: V4 자본 중 운용 비율
        per_stock: V4 자본 중 종목당 비율
        max_pos: 최대 포지션
    
    Returns: 전체 자본 대비 수익률 (decimal)
    """
    if not details: return 0.0, 0.0, 0.0  # (ret, avg_slip, invested_pct)
    n = min(len(details), max_pos)
    invested_pct = min(n * per_stock, working_ratio)
    
    # 각 종목별 slip 계산 (가중 평균)
    slips = []
    for d in details[:n]:
        order_krw = capital_krw * per_stock
        s = slip_spread_pct(d['close']) + slip_impact_pct(order_krw, d['daily_tv'])
        slips.append(s)
    
    avg_slip = np.mean(slips)
    
    # 평균 realized (gap - 수수료 - 슬리피지)
    mean_gap = np.mean([d['gap'] for d in details[:n]])
    mean_realized = (mean_gap - ROUND_TRIP_COST_PCT - avg_slip) / 100
    
    # 전체 자본 대비 수익
    return invested_pct * mean_realized, avg_slip, invested_pct


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
            'calmar': cagr/abs(mdd) if mdd<0 else 0,
            'mean': mean, 'std': std}


# =============================================================================
# [3/3] 자본 규모 × ps 조합 슬리피지 영향 측정
# =============================================================================
print()
print('=' * 115)
print('[3/3] 실전 슬리피지 반영 — 자본 규모 × ps 조합')
print('=' * 115)

CAPITALS = [
    (50_000_000, '5000만'),
    (100_000_000, '1억'),
    (300_000_000, '3억'),
    (500_000_000, '5억'),
    (1_000_000_000, '10억'),
]

PS_GRID = [0.05, 0.07, 0.10]
WORKING_RATIO = 0.30  # §33 권고 고정

print(f'\n  운용 비율 30% 고정')
print(f'  {"자본":<8} {"ps":<6} {"평균slip":>10} {"CAGR":>9} {"MDD":>9} {"Sharpe":>8} '
      f'{"Calmar":>8} {"vs_no_slip":>11}')
print('-' * 115)

# 슬리피지 없는 기준값 먼저 계산
def no_slip_rets(ps):
    rets = []
    for m in samples:
        details = detail_by_month.get(m, [])
        if not details:
            rets.append(0.0); continue
        n = min(len(details), 30)
        inv = min(n * ps, WORKING_RATIO)
        mean_gap = np.mean([d['gap'] for d in details[:n]])
        rets.append(inv * (mean_gap - ROUND_TRIP_COST_PCT) / 100)
    return np.array(rets)

no_slip_stats = {ps: stats(no_slip_rets(ps)) for ps in PS_GRID}

for cap, cap_label in CAPITALS:
    for ps in PS_GRID:
        rets = []; slips = []
        for m in samples:
            r, s, _ = monthly_return_with_slippage(
                detail_by_month.get(m, []), cap, WORKING_RATIO, ps)
            rets.append(r); slips.append(s)
        rets = np.array(rets)
        avg_slip = np.mean(slips)
        s = stats(rets)
        ns = no_slip_stats[ps]
        cagr_loss = s['cagr'] - ns['cagr']
        tag = ' ⭐' if s['calmar'] > 2.5 else ''
        print(f'  {cap_label:<8} {ps:<5.2f} {avg_slip:>9.3f}% {s["cagr"]:>+8.2f}% '
              f'{s["mdd"]:>+8.2f}% {s["sharpe"]:>8.3f} {s["calmar"]:>8.3f} '
              f'{cagr_loss:>+10.2f}%p{tag}')
    print('-' * 115)

# 자본별 ps 최적 선택
print()
print('=' * 115)
print('[자본 규모별 최적 ps 권고]')
print('=' * 115)
print(f'  {"자본":<8} {"최적 ps":<10} {"CAGR":>9} {"MDD":>9} {"Calmar":>8}')
print('-' * 115)

for cap, cap_label in CAPITALS:
    best = None
    for ps in PS_GRID:
        rets = []
        for m in samples:
            r, _, _ = monthly_return_with_slippage(
                detail_by_month.get(m, []), cap, WORKING_RATIO, ps)
            rets.append(r)
        s = stats(np.array(rets))
        if best is None or s['calmar'] > best[1]['calmar']:
            best = (ps, s)
    print(f'  {cap_label:<8} ps={best[0]:.2f}{"":<5} {best[1]["cagr"]:>+8.2f}% '
          f'{best[1]["mdd"]:>+8.2f}% {best[1]["calmar"]:>8.3f}')

# 슬리피지 손실 분포 — 어떤 종목에서 슬리피지 심한가
print()
print('=' * 115)
print('[슬리피지 분포 분석] 자본 1억, ps=0.07')
print('=' * 115)

capital_krw = 100_000_000
ps = 0.07
order_krw = capital_krw * ps  # 700만원
print(f'  종목당 주문 크기: {order_krw/10000:,.0f}만원')
print()

# 모든 종목의 slip 값 수집
all_slips = []; all_closes = []; all_tvs = []; all_participations = []
for m in samples:
    details = detail_by_month.get(m, [])
    for d in details:
        s_spread = slip_spread_pct(d['close'])
        s_impact = slip_impact_pct(order_krw, d['daily_tv'])
        s_total = s_spread + s_impact
        all_slips.append(s_total)
        all_closes.append(d['close'])
        all_tvs.append(d['daily_tv'])
        all_participations.append(order_krw / d['daily_tv'] if d['daily_tv'] > 0 else 0)

all_slips = np.array(all_slips)
all_closes = np.array(all_closes)
all_participations = np.array(all_participations) * 100  # %

print(f'  슬리피지 분포 (총 {len(all_slips)}건):')
print(f'    평균 {all_slips.mean():.3f}%, 중앙값 {np.median(all_slips):.3f}%')
print(f'    최소 {all_slips.min():.3f}%, 최대 {all_slips.max():.3f}%')
print(f'    P90 {np.percentile(all_slips, 90):.3f}%, P95 {np.percentile(all_slips, 95):.3f}%')

# 가격대별 슬리피지
print(f'\n  가격대별 슬리피지:')
price_bins = [(1000, 3000), (3000, 5000), (5000, 10000), (10000, 30000), (30000, 99999999)]
for lo, hi in price_bins:
    mask = (all_closes >= lo) & (all_closes < hi)
    if mask.sum() > 0:
        print(f'    {lo:,}~{hi if hi < 99999999 else "∞":>6}원: '
              f'N={mask.sum():>5}, 평균 slip {all_slips[mask].mean():.3f}%, '
              f'참여율 {all_participations[mask].mean():.2f}%')

# 참여율 5% 초과 (고충격) 비율
high_impact = (all_participations > 5).mean() * 100
print(f'\n  참여율 5% 초과 (high-impact) 비율: {high_impact:.1f}%')

print()
print('완료.')
