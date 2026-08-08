"""_v_57_trade_halt_diagnostic.py — 매매 중단 원인 진단

Seoner 보고: 수일째 자동매매가 전혀 이루어지지 않음.
Phase 3A 패치 (2026-04-22 20:35) 직후 발생 의심.

진단 순서:
  1. trade_log 최근 거래 (언제 마지막 매매?)
  2. v4_observations 상태 (관찰은 되고 있는가?)
  3. scanned_targets_v2 최근 스캔 (매수 후보 공급은 되는가?)
  4. auto_trader 관련 로그 DB 
"""
import sqlite3
from datetime import datetime, timedelta

DB = r'D:\StockAnalyst\trading_system.db'
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('=' * 80)
print('매매 중단 진단')
print(f'현재 시각: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 80)

# 1) trade_log 최근 거래
print('\n[1] trade_log 최근 거래 (언제 마지막?)')
rows = cur.execute("""
    SELECT date, trade_date, code, name, action, price, qty, created_at
    FROM trade_log
    ORDER BY COALESCE(created_at, trade_date) DESC LIMIT 10
""").fetchall()
for r in rows:
    print(f'  {r}')

# 마지막 BUY 만
print('\n[1-b] 마지막 BUY')
last_buy = cur.execute("""
    SELECT date, code, name, price, created_at
    FROM trade_log WHERE UPPER(action)='BUY'
    ORDER BY COALESCE(created_at, date) DESC LIMIT 5
""").fetchall()
for r in last_buy:
    print(f'  {r}')

# 2) v4_observations 상태
print('\n[2] v4_observations (Phase 3A 관찰 작동 여부)')
n = cur.execute("SELECT COUNT(*) FROM v4_observations").fetchone()[0]
print(f'  총 {n} 건')
if n > 0:
    r = cur.execute("""
        SELECT MIN(date), MAX(date), MIN(created_at), MAX(created_at)
        FROM v4_observations
    """).fetchone()
    print(f'  date 범위: {r[0]} ~ {r[1]}')
    print(f'  created_at 범위: {r[2]} ~ {r[3]}')

# 3) scanned_targets_v2 최근 스캔 (매수 후보 공급)
print('\n[3] scanned_targets_v2 최근 스캔 (후보 공급 여부)')
n = cur.execute("SELECT COUNT(*) FROM scanned_targets_v2").fetchone()[0]
print(f'  총 {n} 건')
if n > 0:
    r = cur.execute("""
        SELECT MAX(date), MAX(created_at), COUNT(DISTINCT date)
        FROM scanned_targets_v2
    """).fetchone()
    print(f'  마지막 date: {r[0]}')
    print(f'  마지막 created_at: {r[1]}')
    print(f'  unique dates: {r[2]}')
    
    # 최근 3일 스캔 건수
    print('\n  최근 스캔일 TOP 3:')
    recent = cur.execute("""
        SELECT date(created_at) as d, COUNT(*) FROM scanned_targets_v2
        GROUP BY date(created_at) ORDER BY d DESC LIMIT 5
    """).fetchall()
    for r in recent:
        print(f'    {r[0]}: {r[1]}건')

# 4) 기타 관련 테이블
print('\n[4] auto_trader 관련 테이블 활성도')
for tbl in ['daily_journal', 'daily_performance']:
    try:
        r = cur.execute(f"SELECT MAX(created_at), COUNT(*) FROM {tbl}").fetchone()
        print(f'  {tbl}: 마지막 {r[0]}, 총 {r[1]}건')
    except Exception as e:
        print(f'  {tbl}: 오류 {e}')

conn.close()
print('\n진단 완료.')
