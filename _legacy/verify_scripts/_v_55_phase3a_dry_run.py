"""_v_55_phase3a_dry_run.py — Phase 3A 관찰 모드 격리 검증

검증 항목:
  1. auto_trader import 가능?
  2. _observe_v4_score 메서드 존재?
  3. v4_observations 테이블 INSERT 성공?
  4. 호출부 _check_buy_signals 에 v4_observe 체인 존재?

참고: QApplication / Kiwoom 초기화 없이 class 검사만 수행.
"""
import sys, os
sys.path.insert(0, r'D:\StockAnalyst')
os.chdir(r'D:\StockAnalyst')

# 1) auto_trader 모듈 import (class 정의 검사 목적)
print('[1/5] auto_trader 모듈 import...')
try:
    import auto_trader
    print('  ✅ import 성공')
except Exception as e:
    print(f'  ❌ import 실패: {e}')
    sys.exit(1)

# 2) AutoTrader 클래스 + 새 메서드 존재 확인
print('\n[2/5] _observe_v4_score 메서드 존재 확인...')
# auto_trader 는 AutoTrader 또는 다른 클래스를 가질 수 있음 — 찾기
classes = [c for c in dir(auto_trader) if c[0].isupper() and hasattr(getattr(auto_trader, c), '__dict__')]
print(f'  정의된 클래스: {classes[:10]}')

target_class = None
for cname in classes:
    cls = getattr(auto_trader, cname)
    if hasattr(cls, '_observe_v4_score'):
        target_class = cls
        print(f'  ✅ {cname}._observe_v4_score 발견')
        break

if target_class is None:
    print('  ❌ _observe_v4_score 메서드를 어떤 클래스에서도 못 찾음')
    sys.exit(1)

# 3) 호출부 체인 확인 — _check_buy_signals 내부에 _observe_v4_score 참조?
print('\n[3/5] _check_buy_signals 내부 호출 체인 확인...')
import inspect
check_buy_src = inspect.getsource(target_class._check_buy_signals)
if '_observe_v4_score' in check_buy_src:
    print('  ✅ _check_buy_signals 에 _observe_v4_score 호출 체인 존재')
    # 위치 확인 (cb_check 이후인지)
    lines = check_buy_src.split('\n')
    cb_idx = -1
    obs_idx = -1
    for i, line in enumerate(lines):
        if 'cb_check' in line and 'passed' in line:
            cb_idx = i
        if '_observe_v4_score' in line:
            obs_idx = i
    if cb_idx < obs_idx:
        print(f'  ✅ cb_check (L{cb_idx}) 이후 observe (L{obs_idx}) 위치 — 올바름')
    else:
        print(f'  ⚠ 순서 주의: cb_check L{cb_idx}, observe L{obs_idx}')
else:
    print('  ❌ 호출 체인 미연결')
    sys.exit(1)

# 4) v4_observations 테이블 INSERT 테스트 (격리 — 더미 데이터)
print('\n[4/5] v4_observations 테이블 INSERT 테스트...')
import sqlite3
from datetime import datetime
conn = sqlite3.connect(r'D:\StockAnalyst\trading_system.db', timeout=10)
cur = conn.cursor()

# 더미 INSERT
test_date = '20260422'
test_code = '_TEST_PHASE3A_'
cur.execute("""
    INSERT INTO v4_observations
    (date, code, name, v4_score, total_score, grade, recommendation,
     c1_pattern, c2_new_high, c3_volume, c4_close_pos,
     price, tv_eok, actually_bought, created_at)
    VALUES (?, ?, 'DRY_RUN', 4, 100, 'V4_STRONG', 'STRONG_BUY',
            1, 1, 1, 1, 5000, 300.0, 0, ?)
""", (test_date, test_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
conn.commit()

# 검증
row = cur.execute(
    "SELECT v4_score, recommendation, price, tv_eok FROM v4_observations WHERE code = ?",
    (test_code,)
).fetchone()
if row and row[0] == 4 and row[1] == 'STRONG_BUY':
    print(f'  ✅ INSERT + SELECT 성공: score={row[0]}, rec={row[1]}, price={row[2]}, tv={row[3]}')
else:
    print(f'  ❌ INSERT 후 SELECT 결과 이상: {row}')

# 테스트 데이터 정리
cur.execute("DELETE FROM v4_observations WHERE code = ?", (test_code,))
conn.commit()
print('  테스트 데이터 삭제 완료')

# 5) 전체 테이블 현재 상태
print('\n[5/5] v4_observations 현재 상태')
n = cur.execute("SELECT COUNT(*) FROM v4_observations").fetchone()[0]
print(f'  현재 행수: {n} (빈 상태 정상)')
conn.close()

print('\n✅ Phase 3A Dry-Run 완료 — 실제 자동매매 시 관찰 로직 작동 가능')
