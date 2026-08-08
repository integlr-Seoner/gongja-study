"""_v_60_unified_rankings_trace.py — unified_rankings 후보 공급원 실측

auto_trader 로그 (2026-04-22):
  "unified_rankings에서 25개 후보 조회"
  "매수대상 6개 (종가:5 스윙:1 중장기:0)"

이 5개 종가배팅 후보가 계속 cb_cond=0 종목 → 21일간 매수 0건.

원인 파악:
  1. unified_rankings 테이블의 실체 (뷰? 테이블? SQL?)
  2. 이 테이블이 어떻게 스캔 결과를 선별하는가
  3. scanned_targets_v2 에 cb_cond 통과 18건 있는데 왜 안 골라지는가
"""
import sqlite3

DB = r'D:\StockAnalyst\trading_system.db'
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# 1) unified_rankings 테이블/뷰 존재 확인
print('=' * 80)
print('[1] unified_rankings 관련 객체')
print('=' * 80)

rows = cur.execute("""
    SELECT type, name, sql FROM sqlite_master
    WHERE name LIKE '%unified%' OR name LIKE '%ranking%'
""").fetchall()
for r in rows:
    print(f'\n--- {r[0]}: {r[1]} ---')
    if r[2]:
        print(r[2][:2000])

# 2) unified_rankings 가 테이블이면 내용 확인
print('\n' + '=' * 80)
print('[2] unified_rankings 최근 데이터 (존재 시)')
print('=' * 80)

try:
    cols = cur.execute("PRAGMA table_info(unified_rankings)").fetchall()
    if cols:
        print(f'컬럼: {[c[1] for c in cols]}')
        
        n = cur.execute("SELECT COUNT(*) FROM unified_rankings").fetchone()[0]
        print(f'총 행수: {n:,}')
        
        if n > 0:
            r = cur.execute(
                "SELECT MAX(created_at), MIN(created_at), COUNT(DISTINCT date(created_at)) "
                "FROM unified_rankings"
            ).fetchone()
            print(f'created_at 범위: {r[1]} ~ {r[0]}')
            print(f'unique dates: {r[2]}')
            
            # 최근 10건
            print('\n최근 10건:')
            rows = cur.execute(
                "SELECT * FROM unified_rankings ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            for row in rows:
                print(f'  {row}')
except Exception as e:
    print(f'오류: {e}')

# 3) scanned_targets_v2 와 unified_rankings 연관성
print('\n' + '=' * 80)
print('[3] 4/22 unified_rankings vs scanned_targets_v2 비교')
print('=' * 80)

try:
    # unified_rankings 의 4/22 종가배팅 후보
    unified_422 = cur.execute("""
        SELECT code, name FROM unified_rankings
        WHERE date(created_at) = '2026-04-22'
        ORDER BY created_at DESC LIMIT 30
    """).fetchall()
    print(f'\nunified_rankings 4/22 종목 ({len(unified_422)}개):')
    for r in unified_422[:10]:
        print(f'  {r}')
    
    # scanned_targets_v2 의 4/22 cb 통과 종목
    scan_422 = cur.execute("""
        SELECT code, name, cb_cond1, cb_cond2, cb_cond3 FROM scanned_targets_v2
        WHERE date(created_at) = '2026-04-22'
          AND (cb_cond1=1 OR cb_cond2=1 OR cb_cond3=1)
    """).fetchall()
    print(f'\nscanned_targets_v2 4/22 cb 통과 ({len(scan_422)}개):')
    for r in scan_422[:10]:
        print(f'  {r}')
    
    # 교집합
    unified_codes = set(r[0] for r in unified_422)
    scan_codes = set(r[0] for r in scan_422)
    common = unified_codes & scan_codes
    print(f'\n교집합: {len(common)}개')
    print(f'  공통 종목: {common}')
    print(f'\nunified - scan: {unified_codes - scan_codes}')
    print(f'scan - unified: {scan_codes - unified_codes}')
except Exception as e:
    print(f'오류: {e}')

conn.close()
print('\n완료.')
