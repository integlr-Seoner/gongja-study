"""trade_log 스키마 + 최근 데이터 확인 (actual_return 백필에 필요)"""
import sqlite3

c = sqlite3.connect(r'D:\StockAnalyst\trading_system.db')
cur = c.cursor()

print('=== trade_log schema ===')
cols = cur.execute("PRAGMA table_info(trade_log)").fetchall()
for col in cols:
    print(f'  {col[1]:<20} {col[2]}')

print('\n=== trade_log 행 수 + 기간 ===')
n = cur.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
print(f'rows: {n:,}')
if n > 0:
    r = cur.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT code) FROM trade_log").fetchone()
    print(f'date range: {r[0]} ~ {r[1]}, unique codes: {r[2]}')
    
    print('\n=== 최근 3 BUY 샘플 ===')
    samples = cur.execute(
        "SELECT date, code, name, action, price, qty FROM trade_log "
        "WHERE UPPER(action)='BUY' ORDER BY date DESC LIMIT 3"
    ).fetchall()
    for r in samples:
        print(' ', r)
c.close()
