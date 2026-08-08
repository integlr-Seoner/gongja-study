import sqlite3
c = sqlite3.connect(r'D:\StockAnalyst\trading_system.db')
cur = c.cursor()

print('=== daily_prices schema ===')
cols = cur.execute("PRAGMA table_info(daily_prices)").fetchall()
for col in cols:
    print(f'  {col[1]:<20} {col[2]}')

print('\n=== daily_prices coverage ===')
n = cur.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
date_range = cur.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(DISTINCT code) FROM daily_prices").fetchone()
print(f'  rows: {n:,}')
print(f'  date range: {date_range[0]} ~ {date_range[1]}')
print(f'  unique dates: {date_range[2]}')
print(f'  unique codes: {date_range[3]}')

print('\n=== sample 5 ===')
samples = cur.execute("SELECT * FROM daily_prices LIMIT 3").fetchall()
for r in samples:
    print(' ', r)

c.close()
