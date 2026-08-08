"""_v_64_today_trade_check.py — 오늘 매매 실측"""
import sqlite3
from datetime import datetime

DB = r'D:\StockAnalyst\trading_system.db'
c = sqlite3.connect(DB, timeout=30)
cur = c.cursor()

today = datetime.now().strftime("%Y%m%d")
today_dash = datetime.now().strftime("%Y-%m-%d")
print(f'오늘: {today} ({today_dash})')
print(f'현재 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# 1) 오늘 trade_log
print('[1] 오늘 trade_log')
rows = cur.execute("""
    SELECT date, trade_date, code, name, action, price, qty, created_at
    FROM trade_log
    WHERE date = ? OR trade_date = ? OR date(created_at) = ?
    ORDER BY created_at DESC
""", (today, today_dash, today_dash)).fetchall()
if rows:
    for r in rows:
        print(f'  {r}')
else:
    print('  오늘 거래 기록 없음')

# 2) 최근 3일 trade_log
print('\n[2] 최근 3일 trade_log')
rows = cur.execute("""
    SELECT date, code, name, action, price, qty, created_at
    FROM trade_log
    ORDER BY COALESCE(created_at, date) DESC LIMIT 5
""").fetchall()
for r in rows:
    print(f'  {r}')

# 3) v4_observations 오늘 기록
print('\n[3] v4_observations 오늘')
n_today = cur.execute(
    "SELECT COUNT(*) FROM v4_observations WHERE date = ?", (today,)
).fetchone()[0]
n_total = cur.execute("SELECT COUNT(*) FROM v4_observations").fetchone()[0]
print(f'  오늘 {n_today}건 / 누적 {n_total}건')
if n_total > 0:
    rows = cur.execute("""
        SELECT date, code, name, v4_score, recommendation, created_at
        FROM v4_observations ORDER BY created_at DESC LIMIT 5
    """).fetchall()
    for r in rows:
        print(f'  {r}')

# 4) daily_journal 오늘
print('\n[4] daily_journal 오늘')
row = cur.execute("""
    SELECT journal_date, macro_score, macro_regime, market_vix, market_fgi,
           kospi_change, kosdaq_change, buy_count, sell_count, created_at
    FROM daily_journal WHERE journal_date = ?
""", (today_dash,)).fetchone()
if row:
    print(f'  {row}')
else:
    print('  오늘 기록 없음 (장중이면 정상 — 16:30 경 생성)')

# 5) scanned_targets_v2 오늘
print('\n[5] scanned_targets_v2 오늘 스캔')
row = cur.execute("""
    SELECT COUNT(*),
           SUM(CASE WHEN cb_cond1=1 OR cb_cond2=1 OR cb_cond3=1 THEN 1 ELSE 0 END),
           MAX(created_at)
    FROM scanned_targets_v2
    WHERE date(created_at) = ?
""", (today_dash,)).fetchone()
print(f'  총 {row[0]}건, cb통과 {row[1]}건, 마지막 스캔 {row[2]}')

# 6) unified_rankings 오늘
print('\n[6] unified_rankings 오늘')
row = cur.execute("""
    SELECT COUNT(*), MAX(created_at)
    FROM unified_rankings WHERE date = ?
""", (today,)).fetchone()
print(f'  총 {row[0]}건, 마지막 업데이트 {row[1]}')

c.close()
