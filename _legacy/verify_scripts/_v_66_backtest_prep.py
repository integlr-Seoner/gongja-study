"""_v_66_backtest_prep.py — 백테스트 전 데이터 가용성 확인"""
import sqlite3

# 1) market_condition_history 존재? 데이터 기간?
conn = sqlite3.connect(r'D:\StockAnalyst\trading_system.db')
cur = conn.cursor()
t = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_condition_history'").fetchone()
print(f'market_condition_history 존재: {t is not None}')
if t:
    r = cur.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM market_condition_history").fetchone()
    print(f'  범위: {r[0]} ~ {r[1]}, {r[2]}행')
    
    # 레짐 분포
    dist = cur.execute("SELECT market_condition, COUNT(*) FROM market_condition_history GROUP BY market_condition").fetchall()
    print(f'  분포: {dist}')

# 2) ohlcv_long 기간 확인
conn2 = sqlite3.connect(r'D:\StockAnalyst\ohlcv_long.db')
cur2 = conn2.cursor()
r = cur2.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date), COUNT(DISTINCT code) FROM daily_ohlcv_long").fetchone()
print(f'\nohlcv_long:')
print(f'  기간 {r[0]} ~ {r[1]}')
print(f'  {r[2]}일, {r[3]}종목')

conn.close()
conn2.close()
