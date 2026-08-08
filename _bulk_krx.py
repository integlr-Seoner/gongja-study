# -*- coding: utf-8 -*-
"""90종 일별 시세 벌크 수집 → 캐시 (ⓔⓕ 공용)"""
import io, sys, json, os, time
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\StockAnalyst')
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

OUT = r'D:\StockAnalyst\book_extracts\_krx_90.json'
LOOKBACK = 40

# 90종 이름(엑셀 표기) → 검색 키(괄호 제거)
names = []
firsts = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        key = name.split('(')[0].strip()
        names.append(key)
        ds = [d for t, d, v in recs if t == 'REC']
        if ds: firsts.append((part, name, key, min(ds)))

need = set()
for part, nm, key, d0 in firsts:
    cur, got = d0 - timedelta(days=1), 0
    while got < LOOKBACK:
        if cur.weekday() < 5: need.add(cur.strftime('%Y%m%d')); got += 1
        cur -= timedelta(days=1)
    cur, got = d0, 0
    while got < 6:
        if cur.weekday() < 5: need.add(cur.strftime('%Y%m%d')); got += 1
        cur += timedelta(days=1)

data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
todo = sorted(d for d in need if d not in data)
print('필요 %d일 / 기수집 %d일 / 신규 %d일' % (len(need), len(data), len(todo)))

api = get_krx_api()
t0 = time.time()
for i, d in enumerate(todo, 1):
    try:
        rows = api.get_stock_price_by_date(d)
    except Exception as e:
        rows = []
    keep = {}
    for r in rows:
        n = r.get('name', '')
        for k in names:
            if k and k in n:
                keep[k] = [r['open'], r['high'], r['low'], r['close'], r['change_pct'], r['value']]
                break
    data[d] = keep
    if i % 50 == 0 or i == len(todo):
        el = time.time() - t0
        print('  %d/%d  (%.0f초 경과, 잔여 %.0f분)' % (i, len(todo), el, (len(todo)-i)*el/i/60))
        json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
nz = sum(1 for v in data.values() if v)
print('완료: %d일 저장 (데이터 있는 날 %d일) / 파일 %.1fMB'
      % (len(data), nz, os.path.getsize(OUT)/1e6))
