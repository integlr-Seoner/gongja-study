"""_v_54_create_v4_observations.py — v4_observations 테이블 생성

Phase 3A 관찰 모드 로깅용 테이블.
원칙: 기존 테이블 건드리지 않음. 신규 테이블만 추가.

스키마:
    id             INTEGER PRIMARY KEY
    date           TEXT      YYYYMMDD (관찰 일자)
    code           TEXT      종목코드
    name           TEXT      종목명
    v4_score       INTEGER   0~4
    total_score    INTEGER   v4_score * 25 (호환성)
    grade          TEXT      V4_STRONG / V4_HIGH / ...
    recommendation TEXT      STRONG_BUY / PRIORITY / SKIP / WATCH / NO_SIGNAL
    c1_pattern     INTEGER   0/1 (정배열+장대양봉)
    c2_new_high    INTEGER   0/1 (60일 신고가)
    c3_volume      INTEGER   0/1 (거래대금 3배)
    c4_close_pos   INTEGER   0/1 (종가 95%)
    price          INTEGER   종가
    tv_eok         REAL      거래대금 (억)
    actually_bought INTEGER  0/1 (기존 로직이 실제 매수했는지)
    actual_return  REAL      실제 T+1 수익률 (사후 업데이트용, 초기 NULL)
    created_at     TIMESTAMP
"""
import sqlite3

DB = r'D:\StockAnalyst\trading_system.db'

schema = """
CREATE TABLE IF NOT EXISTS v4_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    v4_score INTEGER,
    total_score INTEGER,
    grade TEXT,
    recommendation TEXT,
    c1_pattern INTEGER,
    c2_new_high INTEGER,
    c3_volume INTEGER,
    c4_close_pos INTEGER,
    price INTEGER,
    tv_eok REAL,
    actually_bought INTEGER DEFAULT 0,
    actual_return REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

index_date_code = "CREATE INDEX IF NOT EXISTS idx_v4obs_date_code ON v4_observations(date, code)"
index_created = "CREATE INDEX IF NOT EXISTS idx_v4obs_created ON v4_observations(created_at DESC)"
index_score = "CREATE INDEX IF NOT EXISTS idx_v4obs_score ON v4_observations(v4_score)"

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# 기존 테이블 확인
existing = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='v4_observations'"
).fetchone()

if existing:
    print('v4_observations 테이블 이미 존재 — 스키마 확인만')
    cols = cur.execute("PRAGMA table_info(v4_observations)").fetchall()
    print(f'컬럼 수: {len(cols)}')
    for col in cols:
        print(f'  {col[1]:<20} {col[2]}')
else:
    cur.execute(schema)
    cur.execute(index_date_code)
    cur.execute(index_created)
    cur.execute(index_score)
    conn.commit()
    print('v4_observations 테이블 생성 완료')
    
    # 검증
    cols = cur.execute("PRAGMA table_info(v4_observations)").fetchall()
    print(f'컬럼 수: {len(cols)}')
    for col in cols:
        print(f'  {col[1]:<20} {col[2]}')
    
    # 인덱스 확인
    indexes = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='v4_observations'"
    ).fetchall()
    print(f'인덱스: {[i[0] for i in indexes]}')

conn.close()
print('\n완료.')
