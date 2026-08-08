# -*- coding: utf-8 -*-
"""ⓔ 준비: 필요 날짜 수 산정 + API 속도 측정"""
import io, sys, time
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\StockAnalyst')
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

LOOKBACK = 40  # 첫 재료일 이전 영업일 수

firsts = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        ds = [d for t, d, v in recs if t == 'REC']
        if ds:
            firsts.append((part, name, min(ds)))

print('종목 %d개 | 첫 재료일 범위: %s ~ %s'
      % (len(firsts), min(f[2] for f in firsts).date(), max(f[2] for f in firsts).date()))

need = set()
for part, name, d0 in firsts:
    cur, got = d0 - timedelta(days=1), 0
    while got < LOOKBACK:
        if cur.weekday() < 5:
            need.add(cur.strftime('%Y%m%d')); got += 1
        cur -= timedelta(days=1)
    # 첫 재료일 자체 + 이후 5일
    cur, got = d0, 0
    while got < 6:
        if cur.weekday() < 5:
            need.add(cur.strftime('%Y%m%d')); got += 1
        cur += timedelta(days=1)

print('★필요 고유 날짜: %d일 (룩백 %d + 이후 5)' % (len(need), LOOKBACK))
print('  → 중복 제거 효과: %d → %d (%.0f%% 절감)'
      % (len(firsts) * (LOOKBACK + 6), len(need),
         100 * (1 - len(need) / (len(firsts) * (LOOKBACK + 6)))))

api = get_krx_api()
t0 = time.time()
api.get_stock_price_by_date('20210324')
t1 = time.time() - t0
print('\nAPI 1일 조회 소요: %.2f초 (KOSPI+KOSDAQ 2콜)' % t1)
print('★예상 총 소요: %d일 × %.2f초 = %.0f분' % (len(need), t1, len(need) * t1 / 60))
