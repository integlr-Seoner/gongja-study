"""_v_58_buy_gate_trace.py — 매수 차단 게이트 단계별 실측

auto_trader._check_buy_signals 의 차단 게이트:
  1. is_running
  2. macro_check (score < 20 or position_scale <= 0)
  3. targets = _get_buy_targets() 비어있는가
  4. holdings 한도 초과
  5. daily_loss_limit 차단
  6. 종목 루프 내:
     - already bought / holding
     - strategy_count < 2
     - price 조회 실패
     - 하한가 게이트
     - material_check (재료)
     - investment_type == '종가배팅' 시 cb_check
"""
import sqlite3
from datetime import datetime

DB = r'D:\StockAnalyst\trading_system.db'
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

print('=' * 80)
print('매수 차단 게이트 진단 (최근 스캔 결과 기준)')
print('=' * 80)

# 1) scanned_targets_v2 최근 스캔의 investment_type 분포
print('\n[1] 최근 스캔 종목의 investment_type / strategy 분포')
latest_date = cur.execute(
    "SELECT MAX(date(created_at)) FROM scanned_targets_v2"
).fetchone()[0]
print(f'  기준일: {latest_date}')

cols = cur.execute("PRAGMA table_info(scanned_targets_v2)").fetchall()
col_names = [c[1] for c in cols]
print(f'  컬럼: {col_names}')

# investment_type 컬럼이 있는지 확인
has_type = 'investment_type' in col_names
has_strat = 'strategy' in col_names
has_count = 'strategy_count' in col_names

# 최근 25건 샘플
print('\n[1-b] 최근 스캔 상위 10건:')
sample = cur.execute(f"""
    SELECT code, name, {'investment_type,' if has_type else ''}
           {'strategy,' if has_strat else ''}
           {'strategy_count,' if has_count else ''}
           cb_cond1, cb_cond2, cb_cond3
    FROM scanned_targets_v2
    WHERE date(created_at) = ?
    ORDER BY created_at DESC LIMIT 10
""", (latest_date,)).fetchall()
for r in sample:
    print(f'  {r}')

# investment_type 분포
if has_type:
    print('\n[1-c] investment_type 분포 (최근 스캔):')
    dist = cur.execute(f"""
        SELECT investment_type, COUNT(*)
        FROM scanned_targets_v2
        WHERE date(created_at) = ?
        GROUP BY investment_type
    """, (latest_date,)).fetchall()
    for r in dist:
        print(f'  {r[0]}: {r[1]}건')

# 2) cb_cond 통과 종목 수 (종가배팅 분기에 도달할 후보)
print('\n[2] cb_cond 최소 1개 통과 종목 (종가배팅 게이트)')
cb_passed = cur.execute(f"""
    SELECT code, name,
           cb_cond1, cb_cond2, cb_cond3, cb_detail
    FROM scanned_targets_v2
    WHERE date(created_at) = ?
      AND (cb_cond1=1 OR cb_cond2=1 OR cb_cond3=1)
    ORDER BY created_at DESC LIMIT 10
""", (latest_date,)).fetchall()
print(f'  총 {len(cb_passed)}건 / 25건 중')
for r in cb_passed[:5]:
    print(f'  {r}')

# 3) 현재 보유 종목 (매수 한도 체크)
print('\n[3] 현재 보유 종목 (max_stocks 한도 체크)')
try:
    holdings = cur.execute("""
        SELECT * FROM sqlite_master WHERE type='table' AND name LIKE '%holding%' OR name LIKE '%position%'
    """).fetchall()
    print(f'  보유 관련 테이블: {[h[1] for h in holdings]}')
except Exception as e:
    print(f'  보유 정보 조회 실패: {e}')

# 4) daily_journal 에서 매수 보류 로그 찾기
print('\n[4] daily_journal 최근 메시지 (매수 관련)')
rows = cur.execute("""
    SELECT created_at, content FROM daily_journal
    ORDER BY created_at DESC LIMIT 20
""").fetchall()
for r in rows[:20]:
    # 길면 자르기
    content = r[1][:150] if r[1] else ''
    print(f'  [{r[0]}] {content}')

conn.close()
print('\n진단 완료.')
