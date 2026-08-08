"""_v_59_deep_gate_trace.py — 깊은 게이트 추적

auto_trader 의 매수 차단 가능 지점:
  A. _get_buy_targets() 가 비어 반환
  B. 이미 holdings 한도 도달 (max_stocks)
  C. investment_type 이 '종가배팅' 이 아니라서 cb_check 게이트 진입조차 못함
  D. daily_loss_limit
  E. 매크로 환경
"""
import sqlite3
from datetime import datetime

DB = r'D:\StockAnalyst\trading_system.db'
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# 1) current_holdings 상태 (max_stocks 한도 체크)
print('=' * 80)
print('[A] 현재 보유 (max_stocks 한도 체크)')
print('=' * 80)

cols = cur.execute("PRAGMA table_info(current_holdings)").fetchall()
print(f'current_holdings 컬럼: {[c[1] for c in cols]}')

rows = cur.execute("SELECT * FROM current_holdings").fetchall()
print(f'\n현재 보유 종목: {len(rows)}개')
for r in rows[:10]:
    print(f'  {r}')

# 2) auto_trader 설정 — max_stocks 가 뭔지 확인
print('\n' + '=' * 80)
print('[B] auto_trader_config (max_stocks 설정)')
print('=' * 80)

# 관련 설정 테이블 검색
all_tables = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%config%' OR name LIKE '%setting%'"
).fetchall()
print(f'설정 관련 테이블: {[t[0] for t in all_tables]}')

# 3) daily_journal 진짜 컬럼명
print('\n' + '=' * 80)
print('[C] daily_journal 실제 컬럼 + 최근 로그')
print('=' * 80)
cols = cur.execute("PRAGMA table_info(daily_journal)").fetchall()
print(f'컬럼: {[c[1] for c in cols]}')

col_names = [c[1] for c in cols]
# text/message/entry 같은 컬럼 찾기
text_col = None
for candidate in ['entry', 'message', 'note', 'log', 'text', 'description', 'journal_text', 'body']:
    if candidate in col_names:
        text_col = candidate
        break

# 최근 20개 로그
if text_col:
    print(f'\n최근 20개 로그 ({text_col} 컬럼):')
    rows = cur.execute(f"""
        SELECT created_at, {text_col} FROM daily_journal
        ORDER BY created_at DESC LIMIT 20
    """).fetchall()
    for r in rows:
        content = (r[1] or '')[:200]
        print(f'  [{r[0]}] {content}')
else:
    # 전체 row 샘플
    print('\n텍스트 컬럼 자동 탐지 실패 — 전체 row 샘플:')
    rows = cur.execute("SELECT * FROM daily_journal ORDER BY created_at DESC LIMIT 5").fetchall()
    for r in rows:
        print(f'  {r}')

# 4) max_stocks 기본값 확인 — auto_trader.py 에서 탐색 필요
print('\n' + '=' * 80)
print('[D] 최근 매도 후 재매수 안 한 이유 추정')
print('=' * 80)

# 4월 2일 이후 scanned_targets 에 cb 통과 종목 얼마나 있었는지
recent_scans = cur.execute("""
    SELECT date(created_at) as d, COUNT(*),
           SUM(CASE WHEN cb_cond1=1 OR cb_cond2=1 OR cb_cond3=1 THEN 1 ELSE 0 END) as cb_pass
    FROM scanned_targets_v2
    WHERE created_at >= '2026-04-02'
    GROUP BY date(created_at)
    ORDER BY d DESC
""").fetchall()
print(f'4/2 이후 일별 스캔 vs cb 통과:')
for r in recent_scans:
    print(f'  {r[0]}: 스캔 {r[1]}건, cb 통과 {r[2]}건')

conn.close()
print('\n진단 완료.')
