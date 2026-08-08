# -*- coding: utf-8 -*-
"""1부+2부 60종 전 기간 시세 수집 (precision용) — 캐시(_krx_90v2.json)에 증분 추가"""
import io, sys, json, os, time
from datetime import timedelta
sys.path.insert(0, r'D:\StockAnalyst'); sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

OUT = r'D:\StockAnalyst\book_extracts\_krx_90v2.json'
CODEMAP = json.load(open(r'D:\StockAnalyst\book_extracts\_code_map.json', encoding='utf-8'))
CODES = {v['code']: k for k, v in CODEMAP.items()}

need=set()
for part in ['1부','2부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        ds=sorted(d for t,d,v in recs if t=='REC')
        if not ds: continue
        c=ds[0]; back=0
        while back<40:
            c-=timedelta(days=1)
            if c.weekday()<5: back+=1
        lo=c; hi=ds[-1]; d=lo
        while d<=hi:
            if d.weekday()<5: need.add(d.strftime('%Y%m%d'))
            d+=timedelta(days=1)

data = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
todo = sorted(d for d in need if d not in data)
print('추가 수집:', len(todo), '일', flush=True)
api = get_krx_api(); t0=time.time()
for i,d in enumerate(todo,1):
    try: rows = api.get_stock_price_by_date(d)
    except Exception: rows=[]
    data[d] = {CODES[r['code']]: [r['open'],r['high'],r['low'],r['close'],r['change_pct'],r['value']]
               for r in rows if r['code'] in CODES}
    if i%30==0 or i==len(todo):
        el=time.time()-t0
        print('  %d/%d (%.0f초, 잔여~%.1f분)'%(i,len(todo),el,(len(todo)-i)*el/i/60), flush=True)
        json.dump(data, open(OUT,'w',encoding='utf-8'), ensure_ascii=False)
json.dump(data, open(OUT,'w',encoding='utf-8'), ensure_ascii=False)
print('완료. 총 캐시', len(data), '일 / 데이터 有', sum(1 for v in data.values() if v), flush=True)
