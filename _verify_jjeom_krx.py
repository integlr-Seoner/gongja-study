# -*- coding: utf-8 -*-
# 쩜상 실증: 쩜상 후보일의 등락률/OHLC/거래대금을 KRX로 확인
import io, sys
sys.path.insert(0, r'D:\StockAnalyst')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api
api = get_krx_api()

# (날짜, 조회명, 라벨) — 개명 반영(2020-11-23 폴라리스=인프라웨어)
targets = [
 ('20201123', '인프라웨어',   '폴라리스 22억(쩜상 확정후보)'),
 ('20200901', 'KEC',        'KEC 23억(쩜상 확정후보)'),
 ('20210726', '세종메디칼',   '세종 35억(★미확정)'),
 ('20211208', '세종메디칼',   '세종 2,869억(상한가·대량=대조군)'),
]
for date, name, label in targets:
    try:
        rows = api.get_stock_price_by_date(date, limit=4000)
        hit = [r for r in rows if r.get('name') == name]
        if not hit:
            # 부분일치 백업
            hit = [r for r in rows if name in str(r.get('name'))]
        if not hit:
            print('[%s] %-10s 미발견 (총 %d행)' % (date, name, len(rows))); continue
        r = hit[0]
        val_eok = r['value']/1e8
        body = abs(r['close']-r['open'])
        rng = r['high']-r['low']
        print('%s | %s' % (date, label))
        print('   등락률 %+.2f%% | O %d H %d L %d C %d | 몸통 %d 범위 %d | 거래대금 %.0f억 | 거래량 %d'
              % (r['change_pct'], r['open'], r['high'], r['low'], r['close'], body, rng, val_eok, r['volume']))
    except Exception as e:
        print('[%s] %s 실패: %s' % (date, name, e))
