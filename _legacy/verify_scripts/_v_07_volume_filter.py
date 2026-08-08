"""검증: MIN_VOLUME=50000 유동성 필터의 자격 필터 타당성
근본: 거래량 구간별 위험 지표가 체계적으로 다른지 확인
  - 단독 효과: 전체 종목에서 거래량 구간별
  - 증분 효과: MIN_PRICE>=1000 통과 후 거래량 구간별 (자격 필터 조합)

거래량 구간: <1만, 1만-5만, 5만-10만, 10만-50만, 50만+
위험 지표: 상폐율(120d), 극단하락(20d -30%↓), 20일변동성, 거래정지비율

샘플: 2014-01 ~ 2023-12 월 단위 중순 (120영업일 추적 가능)
"""
import sqlite3
import numpy as np
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
conn = sqlite3.connect(DB, timeout=30)

all_dates = [r[0] for r in conn.execute("""
    SELECT DISTINCT date FROM daily_ohlcv_long
    WHERE date >= '20140101' AND date <= '20231231'
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


def get_future_dates(asof, n):
    r = conn.execute("""
        SELECT DISTINCT date FROM daily_ohlcv_long
        WHERE date > ? ORDER BY date ASC LIMIT ?
    """, (asof, n)).fetchall()
    return [x[0] for x in r]


def classify_vol(v):
    if v < 10000: return '<1만'
    if v < 50000: return '1만-5만'
    if v < 100000: return '5만-10만'
    if v < 500000: return '10만-50만'
    return '50만+'


vol_buckets = ['<1만', '1만-5만', '5만-10만', '10만-50만', '50만+']

# 두 관점: (A) 전체 (B) price>=1000 전제
# {bucket: {...}}
def make_bucket(): return {'total':0, 'delisted':0, 'crash30':0,
                            'vols':[], 'stop_days':0, 'total_days':0}
agg_all = {b: make_bucket() for b in vol_buckets}
agg_priced = {b: make_bucket() for b in vol_buckets}

for i, asof in enumerate(samples, 1):
    # 오늘 전 종목 (close>0, OHL 정합성만 체크, 가격/거래량 필터 없음)
    today = conn.execute("""
        SELECT code, close, volume
        FROM daily_ohlcv_long
        WHERE date = ? AND close > 0
          AND close BETWEEN low AND high
    """, (asof,)).fetchall()
    if not today:
        continue

    future_20 = get_future_dates(asof, 20)
    if len(future_20) < 20:
        continue
    last_20 = future_20[-1]

    future_120 = get_future_dates(asof, 120)
    t120 = future_120[-1] if len(future_120) >= 120 else None

    codes = [c for c, _, _ in today]
    ph = ','.join('?' * len(codes))

    # T+1~T+20 OHLCV 한 번에 로드
    rows_fut = conn.execute(f"""
        SELECT code, date, open, high, low, close, volume
        FROM daily_ohlcv_long
        WHERE code IN ({ph}) AND date > ? AND date <= ?
    """, codes + [asof, last_20]).fetchall()

    fut_by_code = defaultdict(list)
    for code, d, o, h, l, c, v in rows_fut:
        fut_by_code[code].append((o, h, l, c, v))

    # T+120 존재 여부
    exists_120 = set()
    if t120:
        t120_rows = conn.execute(f"""
            SELECT DISTINCT code FROM daily_ohlcv_long
            WHERE code IN ({ph}) AND date > ? AND date <= ?
        """, codes + [last_20, t120]).fetchall()
        exists_120 = {x[0] for x in t120_rows}


    for code, p0, v0 in today:
        vb = classify_vol(v0)
        fut = fut_by_code.get(code, [])

        for target in (agg_all, agg_priced if p0 >= 1000 else None):
            if target is None:
                continue
            a = target[vb]
            a['total'] += 1

            # A. 상폐
            if t120 is not None and code not in exists_120:
                a['delisted'] += 1

            if not fut:
                continue

            # B. 극단 하락 -30%↓
            lows_20 = [l for o, h, l, c, v in fut[:20] if l > 0]
            if lows_20 and p0 > 0:
                dd = (min(lows_20) / p0 - 1) * 100
                if dd <= -30:
                    a['crash30'] += 1

            # C. 변동성 (종가 기준 일일 수익률 std)
            closes = [c for o, h, l, c, v in fut[:20] if c > 0]
            if len(closes) >= 5:
                prev = p0
                rets = []
                for c in closes:
                    if prev > 0:
                        rets.append((c/prev - 1)*100)
                    prev = c
                if len(rets) >= 5:
                    a['vols'].append(np.std(rets))

            # D. 거래정지 (volume=0)
            for o, h, l, c, v in fut[:20]:
                a['total_days'] += 1
                if v == 0:
                    a['stop_days'] += 1

    if i % 12 == 0:
        print(f'  {i}/{len(samples)}')

conn.close()


def summarize(agg, title):
    print()
    print('=' * 100)
    print(title)
    print('=' * 100)
    print(f'{"거래량구간":<12} {"관측":>10} {"상폐율":>10} {"극단하락":>10} {"변동성":>10} {"거래정지":>10}')
    print('-' * 80)
    for b in vol_buckets:
        a = agg[b]
        if a['total'] == 0:
            continue
        d = a['delisted']/a['total']*100
        c = a['crash30']/a['total']*100
        v = np.mean(a['vols']) if a['vols'] else 0
        s = a['stop_days']/a['total_days']*100 if a['total_days'] else 0
        print(f'  {b:<12} {a["total"]:>10,} '
              f'{d:>8.3f}%   {c:>8.2f}%   {v:>8.3f}   {s:>8.3f}%')

    # 컷오프 비교: <5만 vs >=5만
    under = make_bucket()
    over = make_bucket()
    for b in ['<1만', '1만-5만']:
        for k in ('total','delisted','crash30','stop_days','total_days'):
            under[k] += agg[b][k]
        under['vols'].extend(agg[b]['vols'])
    for b in ['5만-10만', '10만-50만', '50만+']:
        for k in ('total','delisted','crash30','stop_days','total_days'):
            over[k] += agg[b][k]
        over['vols'].extend(agg[b]['vols'])

    print(f'\n  [컷오프 비교 MIN_VOLUME=50000]')
    for lbl, a in [('<5만 (제외)', under), ('>=5만 (통과)', over)]:
        if a['total'] == 0:
            continue
        d = a['delisted']/a['total']*100
        c = a['crash30']/a['total']*100
        v = np.mean(a['vols']) if a['vols'] else 0
        s = a['stop_days']/a['total_days']*100 if a['total_days'] else 0
        print(f'  {lbl:<14} {a["total"]:>10,} '
              f'{d:>8.3f}%   {c:>8.2f}%   {v:>8.3f}   {s:>8.3f}%')

    if over['total'] and under['total']:
        r_d = (under['delisted']/under['total'])/max(over['delisted']/over['total'],1e-9)
        r_c = (under['crash30']/under['total'])/max(over['crash30']/over['total'],1e-9)
        r_v = (np.mean(under['vols']) if under['vols'] else 0)/max(np.mean(over['vols']) if over['vols'] else 1e-9, 1e-9)
        r_s = (under['stop_days']/max(under['total_days'],1))/max(over['stop_days']/max(over['total_days'],1), 1e-9)
        print(f'\n  배율 (<5만 / >=5만):')
        print(f'    상폐율     {r_d:.2f}배')
        print(f'    극단하락   {r_c:.2f}배')
        print(f'    변동성     {r_v:.2f}배')
        print(f'    거래정지   {r_s:.2f}배')


summarize(agg_all, '[A] 전체 종목 — 거래량 단독 효과 (가격 필터 미적용)')
summarize(agg_priced, '[B] MIN_PRICE>=1000 통과 후 — 거래량 증분 효과')
