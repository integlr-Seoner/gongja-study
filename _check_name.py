# -*- coding: utf-8 -*-
"""이름 매칭 검증 — 부분일치(k in n)가 오종목을 잡는지"""
import io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'D:\StockAnalyst')
from krx_api import get_krx_api

api = get_krx_api()
CHECK = [('바이오니아', '20210702', 3882), ('이씨에스', '20200821', 1),
         ('유니온', '20200504', 347), ('우리기술', '20210604', 763)]

for key, d, exl in CHECK:
    rows = api.get_stock_price_by_date(d)
    hits = [r for r in rows if key in str(r.get('name', ''))]
    print('=' * 76)
    print('검색어 %r | %s | 엑셀 %s억 | 부분일치 %d건' % (key, d, exl, len(hits)))
    for r in hits:
        print('   %-8s %-16s %-8s 종가%8d %+7.2f%% 거래대금 %8.0f억'
              % (r['code'], r['name'], r['market'], r['close'], r['change_pct'], r['value']/1e8))
