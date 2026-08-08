# -*- coding: utf-8 -*-
"""90종 일별 시세 벌크 수집 v2 — ★종목코드 정확일치 (개명/부분일치 무관)"""
import io, sys, json, os, time
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\StockAnalyst')
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

OUT = r'D:\StockAnalyst\book_extracts\_krx_90v2.json'
CODEMAP = json.load(open(r'D:\StockAnalyst\book_extracts\_code_map.json', encoding='utf-8'))
CODES = {v['code']: k for k, v in CODEMAP.items()}   # code → 엑셀 종목명
LOOKBACK = 40

need = set()
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        ds = sorted(d for t, d, v in recs if t == 'REC')
        if not ds: continue
        cur, got = ds[0] - timedelta(days=1), 0
        while got < LOOKBACK:
            if cur.weekday() < 5: need.add(cur.strftime('%Y%m%d')); got += 1
            cur -= timedelta(days=1)
        cur, got = ds[0], 0
        while got < 6:
            if cur.weekday() < 5: need.add(cur.strftime('%Y%m%d')); got += 1
            cur += timedelta(days=1)

data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
todo = sorted(d for d in need if d not in data)
print('필요 %d일 / 기수집 %d / 신규 %d | ★코드 기준 %d종' % (len(need), len(data), len(todo), len(CODES)))

api = get_krx_api()
t0 = time.time()
for i, d in enumerate(todo, 1):
    try:
        rows = api.get_stock_price_by_date(d)
    except Exception:
        rows = []
    data[d] = {CODES[r['code']]: [r['open'], r['high'], r['low'], r['close'], r['change_pct'], r['value']]
               for r in rows if r['code'] in CODES}
    if i % 60 == 0 or i == len(todo):
        el = time.time() - t0
        print('  %d/%d (%.0f초, 잔여 %.1f분)' % (i, len(todo), el, (len(todo)-i)*el/i/60))
        json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
print('완료 %d일 / 데이터 有 %d일 / %.1fMB'
      % (len(data), sum(1 for v in data.values() if v), os.path.getsize(OUT)/1e6))
