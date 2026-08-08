# -*- coding: utf-8 -*-
"""ⓖ K 권고 검정 — 쩜상 해제일 진입 vs 익일/2일후 진입 수익률"""
import io, sys, json, os
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\StockAnalyst')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

CACHE = r'D:\StockAnalyst\book_extracts\_krx_cache.json'
api = get_krx_api()
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}

def day(d):
    """d(YYYYMMDD) 전 종목 시세. 캐시 사용."""
    if d in cache:
        return cache[d]
    try:
        rows = api.get_stock_price_by_date(d)
    except Exception:
        rows = []
    cache[d] = {r['name']: [r['open'], r['high'], r['low'], r['close'], r['change_pct'], r['value']]
                for r in rows}
    return cache[d]

def series(nm, start, n):
    """nm 종목의 start부터 영업일 n개 시세"""
    out, cur, got = [], datetime.strptime(start, '%Y%m%d'), 0
    while got < n and (cur - datetime.strptime(start, '%Y%m%d')).days < n * 3:
        ds = cur.strftime('%Y%m%d')
        if cur.weekday() < 5:
            d = day(ds)
            hit = next((v for k, v in d.items() if nm in k), None)
            if hit:
                out.append((ds, hit)); got += 1
        cur += timedelta(days=1)
    return out

EVENTS = [  # (종목명, 쩜상일)
    ('승일', '20210323'), ('에코캡', '20210930'), ('동신건설', '20201221'),
    ('인프라웨어', '20201123'), ('KEC', '20200901'), ('세종메디칼', '20210726'),
    ('동신건설', '20201218'),
]

print('%-11s %-9s | %-9s %-8s %-7s | %s' % ('종목', '쩜상일', '해제일', '해제종가', '거래대금', 'D+1 / D+3 / D+5 / D+10 수익률(해제일 종가 기준)'))
print('-' * 118)
for nm, d0 in EVENTS:
    s = series(nm, d0, 13)
    if len(s) < 3:
        print('%-11s %-9s | 데이터 부족(%d)' % (nm, d0, len(s))); continue
    # 쩜상 = O=H=L=C and pct>=29 → 해제일 = 그 이후 첫 "거래가 있는 비쩜상일"
    # ★거래대금 ≈ 0 = 거래정지일 → 해제일로 잡으면 안 됨 (동신건설 2020-12-22~23)
    rel = None
    halted = []
    for i, (ds, v) in enumerate(s):
        o, h, l, c, p, val = v
        if i == 0:
            continue
        if val < 5e7:                     # 거래정지(거래대금 5천만 미만)
            halted.append(ds); continue
        jj = (p >= 29) and (o == h == l == c)
        if not jj:
            rel = i; break
    if rel is None:
        print('%-11s %-9s | 해제일 미발견(연속 쩜상?)' % (nm, d0)); continue
    rds, rv = s[rel]
    base = rv[3]
    outs = []
    for k in (1, 3, 5, 10):
        j = rel + k
        outs.append('%+6.1f%%' % (100 * (s[j][1][3] / base - 1)) if j < len(s) else '   -  ')
    note = ('  ※정지 %d일' % len(halted)) if halted else ''
    print('%-11s %-9s | %-9s %8d %7d억 | %s%s'
          % (nm, d0, rds, base, round(rv[5] / 1e8), ' / '.join(outs), note))

json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
print('\n캐시: %d일치 저장' % len(cache))
