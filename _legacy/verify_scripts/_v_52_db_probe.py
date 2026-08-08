import sqlite3
# OHLCV 데이터 보유 DB 확인
for db_name in ['ohlcv_long.db', 'trading_system.db']:
    p = rf'D:\StockAnalyst\{db_name}'
    c = sqlite3.connect(p)
    cur = c.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%ohlcv%' OR name LIKE '%daily%'").fetchall()
    print(f'{db_name}: {tables}')
    c.close()
