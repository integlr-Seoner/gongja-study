# -*- coding: utf-8 -*-
"""KRX Open API 가용성 + 과거 데이터 소급 확인"""
import io, sys, os
sys.path.insert(0, r'D:\StockAnalyst')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

api = get_krx_api()
print('API 키 존재:', bool(api.api_key), '| 길이:', len(api.api_key) if api.api_key else 0)
print('BASE_URL:', api.BASE_URL)
print()

# 1) 최근 영업일
try:
    recent = api.get_stock_price_by_date(limit=3)
    print('[최근 영업일] %d건' % len(recent))
    for r in recent[:3]:
        print('   ', r)
except Exception as e:
    print('[최근] 실패:', e)
print()

# 2) 과거 소급 — 쩜상 검증 대상일
for d in ['20200901', '20201123', '20210323', '20210930']:
    try:
        rows = api.get_stock_price_by_date(d, limit=2)
        print('[%s] %d건  %s' % (d, len(rows), (rows[0].get('name') if rows else '-')))
    except Exception as e:
        print('[%s] 실패: %s' % (d, e))
