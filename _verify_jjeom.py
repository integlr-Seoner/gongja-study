# -*- coding: utf-8 -*-
"""ⓓ 쩜 상한가 실측 검증 — G986의 6건 OHLC 확인"""
import io, sys
sys.path.insert(0, r'D:\StockAnalyst')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

# G986의 <100억 레코드 (쩜상 후보). (종목명검색어, 날짜, 엑셀 거래대금(억), 재료)
TARGETS = [
    ('승일',        '20210323',  17, '윤석열 관련주 부각에 연일 강세'),
    ('에코캡',      '20210930',  18, '리비안 美 상장 소식에 주가 강세 지속'),
    ('동신건설',    '20201221',  19, '안철수 뜨자 이재명 관련주 동신건설 상한가..'),
    ('인프라웨어',  '20201123',  22, '가상화폐 폴라 상장 영향에 상한가 지속'),
    ('KEC',         '20200901',  23, '테슬라 반도체 공급에 이틀 연속 상한가'),
    ('세종메디칼',  '20210726',  35, '경영권 팔린다는 소식에 주가 강세 지속'),
    ('동신건설',    '20201218',  79, '이재명 지사 고향에 있다는 이유로 상한가'),
    # 대조군: 쩜상이 아닌 것으로 예상되는 정상 거래일
    ('에코캡',      '20211001', 1649, '(대조군) 리비안 기대감 폭발에 연일 상한가'),
    ('승일',        '20210324', 815, '(대조군) 윤석열 전 총장과 관련 없다.. 뉴스 보도'),
]

api = get_krx_api()
cache = {}
print('%-12s %-10s %-7s %-7s %-7s %-7s %-8s %-9s %-10s %s'
      % ('종목', '날짜', '시가', '고가', '저가', '종가', '등락률', '거래대금(억)', '엑셀(억)', '판정'))
print('-' * 132)
for nm, d, exl, memo in TARGETS:
    if d not in cache:
        try:
            cache[d] = api.get_stock_price_by_date(d)
        except Exception as e:
            print('%-12s %-10s API 실패: %s' % (nm, d, e)); continue
    rows = [r for r in cache[d] if nm in str(r.get('name', ''))]
    if not rows:
        print('%-12s %-10s ★종목 미발견' % (nm, d)); continue
    r = rows[0]
    o, h, l, c = r['open'], r['high'], r['low'], r['close']
    pct = r['change_pct']
    val_ok = round(r['value'] / 1e8)           # 원 → 억
    # 쩜상 판정: 등락률 +29% 이상 AND 시가=고가=저가=종가
    jjeom = (pct >= 29) and (o == h == l == c)
    sang  = pct >= 29
    verdict = '★★쩜상 확정' if jjeom else ('★상한가(쩜상 아님)' if sang else '일반')
    print('%-12s %-10s %-7s %-7s %-7s %-7s %6.2f%% %9d %10d  %s'
          % (r['name'][:11], d, o, h, l, c, pct, val_ok, exl, verdict))
