"""종가배팅 재검증 — close-to-next-open (gap_ret) 기반
종가배팅 구조:
  T일 장 종료 즈음 매수 → T+1일 시가 매도 (KRX 09:00 또는 NXT 08:00)
  수익률 = T+1.open / T.close - 1

본 검증은 '스크리너 각 단계가 gap_ret에 어떤 효과를 주는가' 측정.
  1. 베이스라인: 전체 유효 종목의 gap_ret 분포 (랜덤 매수)
  2. 자격 필터(MIN_PRICE>=1000, MIN_VOLUME>=50000) 통과의 gap_ret
  3. 거래대금 상위 N의 gap_ret (자격 통과 내부)
  4. 60일 신고가 돌파의 gap_ret

지표:
  - 평균·중앙 gap_ret (%)
  - 승률 (gap_ret > 0)
  - 갭업 1%+ / 3%+ / 5%+ 포착률
  - 갭다운 -1%↓ / -3%↓ 발생률
  - 수수료+세금 차감 순수익 (한국주식 편도 약 0.23% × 2 = 0.46%)
  - 분포 표준편차

샘플: 2014-01 ~ 2026-04 월 단위 중순 (약 148개 날짜 × 수천 종목)
"""
import sqlite3
import numpy as np

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000
ROUND_TRIP_COST_PCT = 0.46  # 매수+매도 수수료·세금 합계 (%)

conn = sqlite3.connect(DB, timeout=30)

all_dates = [r[0] for r in conn.execute("""
    SELECT DISTINCT date FROM daily_ohlcv_long
    WHERE date >= '20140101' AND date <= '20260417'
    ORDER BY date
""").fetchall()]

samples = []
current_ym = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != current_ym and dd >= 15:
        samples.append(d)
        current_ym = ym

print(f'샘플 날짜: {len(samples)}개')
print()

# -----------------------------------------------------------------------------
# 유틸: 한 날짜의 {code: row} 조회
# row = (open, high, low, close, volume)
# -----------------------------------------------------------------------------
def fetch_day(cur, d: str) -> dict:
    """특정 날짜의 전종목 OHLCV 딕셔너리 반환"""
    out = {}
    for code, o, h, lo, cl, v in cur.execute(
        "SELECT code, open, high, low, close, volume FROM daily_ohlcv_long WHERE date = ?",
        (d,)
    ):
        out[code] = (o, h, lo, cl, v)
    return out


def next_business_day(dates_list, d: str):
    """dates_list에서 d 직후의 날짜 반환 (없으면 None)"""
    try:
        i = dates_list.index(d)
        return dates_list[i + 1] if i + 1 < len(dates_list) else None
    except ValueError:
        return None


# -----------------------------------------------------------------------------
# 60일 신고가 조회 (자격 통과 종목만 대상)
# -----------------------------------------------------------------------------
def fetch_60d_highs(cur, codes: list, d: str) -> dict:
    """T-60~T-1의 각 종목 최고종가 반환. codes는 자격 통과 종목 리스트."""
    if not codes:
        return {}
    # 60 영업일 전 날짜 추정 (달력일 기준 90일 — 안전 버퍼)
    from datetime import datetime, timedelta
    d_dt = datetime.strptime(d, '%Y%m%d')
    start = (d_dt - timedelta(days=90)).strftime('%Y%m%d')

    out = {}
    # 한 번의 쿼리로 처리 (IN 절)
    placeholder = ','.join('?' * len(codes))
    rows = cur.execute(
        f"""SELECT code, MAX(close) FROM daily_ohlcv_long
            WHERE code IN ({placeholder}) AND date >= ? AND date < ?
            GROUP BY code""",
        (*codes, start, d)
    ).fetchall()
    for code, mx in rows:
        out[code] = mx
    return out


# -----------------------------------------------------------------------------
# 메인 루프: 각 샘플 날짜에서 4개 그룹의 gap_ret 수집
# -----------------------------------------------------------------------------
cur = conn.cursor()

# 결과 저장용 numpy array
base_gaps = []         # 그룹1: 베이스라인 (유효 거래만)
qualify_gaps = []      # 그룹2: 자격 필터 통과
top200_gaps = []       # 그룹3: 자격 통과 내 거래대금 Top200
newhigh60_gaps = []    # 그룹4: 자격 통과 내 60일 신고가 돌파

for idx, d in enumerate(samples):
    t1 = next_business_day(all_dates, d)
    if t1 is None:
        continue

    day_t = fetch_day(cur, d)
    day_t1 = fetch_day(cur, t1)
    if not day_t or not day_t1:
        continue

    # -------- 그룹1 베이스라인: 유효거래 전체 --------
    # 유효성: T.close > 0, T+1.open > 0, T+1 에 해당 종목 존재, 보통주(끝자리 0)
    codes_all = []
    for code, (o, h, lo, cl, v) in day_t.items():
        if code not in day_t1:
            continue
        if not code.endswith('0'):
            continue
        n_open = day_t1[code][0]
        if cl <= 0 or n_open <= 0:
            continue
        gap = (n_open / cl - 1) * 100
        base_gaps.append(gap)

        # -------- 그룹2 자격필터 통과 --------
        if cl >= MIN_PRICE and v >= MIN_VOL:
            qualify_gaps.append(gap)
            codes_all.append((code, cl * v, gap))  # (code, 거래대금, gap)

    # -------- 그룹3 거래대금 Top 200 (자격 통과 내) --------
    codes_all.sort(key=lambda x: -x[1])
    for _code, _val, _gap in codes_all[:200]:
        top200_gaps.append(_gap)

    # -------- 그룹4 60일 신고가 돌파 (자격 통과 내) --------
    qualify_codes = [x[0] for x in codes_all]
    highs60 = fetch_60d_highs(cur, qualify_codes, d)
    for code, _val, _gap in codes_all:
        t_close = day_t[code][3]
        prev_high = highs60.get(code)
        if prev_high is not None and t_close > prev_high:
            newhigh60_gaps.append(_gap)

    if (idx + 1) % 20 == 0:
        print(f'  진행: {idx+1}/{len(samples)} ({d})')

print()
print(f'수집 완료: base={len(base_gaps)}, qualify={len(qualify_gaps)}, top200={len(top200_gaps)}, newhigh60={len(newhigh60_gaps)}')
print()


# -----------------------------------------------------------------------------
# 통계 출력
# -----------------------------------------------------------------------------
def stats(name: str, arr: list):
    if not arr:
        print(f'[{name}] 데이터 없음')
        return
    a = np.array(arr, dtype=np.float64)
    n = len(a)
    mean = a.mean()
    median = np.median(a)
    std = a.std()
    winrate = (a > 0).sum() / n * 100

    # 갭업·갭다운 포착률
    gu1 = (a >= 1).sum() / n * 100
    gu3 = (a >= 3).sum() / n * 100
    gu5 = (a >= 5).sum() / n * 100
    gd1 = (a <= -1).sum() / n * 100
    gd3 = (a <= -3).sum() / n * 100

    # 수수료·세금 차감 후 순수익 기대값
    realized_mean = mean - ROUND_TRIP_COST_PCT
    conservative_mean = mean - 0.76

    print(f'[{name}]')
    print(f'  N={n:,}')
    print(f'  평균={mean:+.3f}%  중앙={median:+.3f}%  표준편차={std:.3f}%')
    print(f'  승률(gap>0)={winrate:.2f}%')
    print(f'  갭업 1%+={gu1:.2f}%  3%+={gu3:.2f}%  5%+={gu5:.2f}%')
    print(f'  갭다운 -1%↓={gd1:.2f}%  -3%↓={gd3:.2f}%')
    print(f'  realized_mean(수수료차감)={realized_mean:+.3f}%')
    print(f'  conservative_mean(슬리피지포함)={conservative_mean:+.3f}%')
    print()


print('=' * 70)
print('gap_ret 분포 비교 — 베이스라인 / 자격통과 / Top200 / 60일신고가')
print('=' * 70)
print()

stats('그룹1 베이스라인(유효거래)', base_gaps)
stats('그룹2 자격필터통과(>=1000, >=50K)', qualify_gaps)
stats('그룹3 거래대금 Top200(자격內)', top200_gaps)
stats('그룹4 60일신고가 돌파(자격內)', newhigh60_gaps)

# 증분 효과 (그룹1 대비)
if base_gaps and qualify_gaps and top200_gaps and newhigh60_gaps:
    b_mean = np.mean(base_gaps)
    print('=' * 70)
    print('베이스라인 대비 평균 gap_ret 증분')
    print('=' * 70)
    print(f'  자격필터 통과 - 베이스라인 = {np.mean(qualify_gaps) - b_mean:+.3f}%p')
    print(f'  Top200       - 베이스라인 = {np.mean(top200_gaps) - b_mean:+.3f}%p')
    print(f'  60일 신고가 돌파 - 베이스라인 = {np.mean(newhigh60_gaps) - b_mean:+.3f}%p')

conn.close()
print()
print('완료.')
