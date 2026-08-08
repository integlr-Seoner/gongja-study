"""검증 사전 조사: 날짜별 유효 종목 수"""
import sqlite3

conn = sqlite3.connect(r'D:\StockAnalyst\ohlcv_long.db', timeout=30)
c = conn.cursor()

r = c.execute("""
    SELECT date, COUNT(*) as n
    FROM daily_ohlcv_long
    WHERE volume > 0 AND close BETWEEN low AND high
    GROUP BY date
    ORDER BY date
""").fetchall()

print(f'유효 영업일 수: {len(r)}개')
print(f'범위: {r[0][0]} ~ {r[-1][0]}')
print()

# 각 기간별 평균 종목 수
periods = [
    ('1996-2000', '19960101', '20001231'),
    ('2001-2005', '20010101', '20051231'),
    ('2006-2010', '20060101', '20101231'),
    ('2011-2015', '20110101', '20151231'),
    ('2016-2020', '20160101', '20201231'),
    ('2021-2026', '20210101', '20261231'),
]
for label, start, end in periods:
    sub = [(d, n) for d, n in r if start <= d <= end]
    if sub:
        avg_n = sum(n for _, n in sub) / len(sub)
        print(f'  {label}: {len(sub):>4}일, 평균 {avg_n:>5.0f}개 유효 종목/일')

# 매수 가능 조건 추가 (MIN_PRICE=1000, MIN_VOLUME=50000)
print('\n--- MIN_PRICE=1000, MIN_VOLUME=50000 필터 적용 시 ---')
r2 = c.execute("""
    SELECT date, COUNT(*) as n
    FROM daily_ohlcv_long
    WHERE volume >= 50000 AND close >= 1000
      AND close BETWEEN low AND high
    GROUP BY date
    ORDER BY date
""").fetchall()
for label, start, end in periods:
    sub = [(d, n) for d, n in r2 if start <= d <= end]
    if sub:
        avg_n = sum(n for _, n in sub) / len(sub)
        print(f'  {label}: {len(sub):>4}일, 평균 {avg_n:>5.0f}개')

conn.close()
