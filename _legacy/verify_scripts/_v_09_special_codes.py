"""특수 코드 32개 (영문 포함) 실제 데이터 확인
DART 기업코드이지만 실제 주식 코드가 아닐 가능성
"""
import sqlite3

DB = r'D:\StockAnalyst\ohlcv_long.db'
conn = sqlite3.connect(DB, timeout=30)

rows = conn.execute("""
    SELECT DISTINCT code FROM daily_ohlcv_long
    WHERE code GLOB '*[A-Z]*'
""").fetchall()

codes = [r[0] for r in rows]
print(f'특수 코드 (영문 포함): {len(codes)}개')

# 각 코드의 데이터 현황
for c in codes[:10]:
    r = conn.execute("""
        SELECT COUNT(*), MIN(date), MAX(date),
               SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END)
        FROM daily_ohlcv_long WHERE code = ?
    """, (c,)).fetchone()
    total, min_d, max_d, active = r
    print(f'  {c}: {total:,}행 ({min_d}~{max_d})  거래량>0: {active:,}일')

# trading_system.db의 dart_corp_codes와 조인해 이름 확인
src = sqlite3.connect(r'D:\StockAnalyst\trading_system.db', timeout=30)
ph = ','.join('?' * len(codes))
names = src.execute(f"""
    SELECT stock_code, corp_name
    FROM dart_corp_codes
    WHERE stock_code IN ({ph})
    LIMIT 15
""", codes).fetchall()
print('\n이름 조회 (상위 15개):')
for c, n in names:
    print(f'  {c}: {n}')
src.close()
conn.close()
