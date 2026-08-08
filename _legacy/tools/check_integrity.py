"""Phase 0-5: 데이터 정합성 자동 검증 스크립트
check_integrity.py - epoch-aware 버전
"""
import sqlite3
import sys
from datetime import datetime

def check_integrity(verbose=False):
    """전체 데이터 정합성 검사. 에러 수 반환."""
    errors = 0
    warnings = 0
    
    conn = sqlite3.connect('trading_system.db')
    try:
        c = conn.cursor()
    
        print("=" * 60)
        print(f"[INTEGRITY CHECK] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
    
        # epoch 확인
        c.execute("SELECT start_date FROM system_epochs ORDER BY start_date ASC LIMIT 1")
        epoch_row = c.fetchone()
        epoch = epoch_row[0] if epoch_row else None
        if epoch:
            print(f"  [INFO] epoch: {epoch}")
    
        # 1. action NULL 검사
        c.execute("SELECT COUNT(*) FROM trade_log WHERE action IS NULL")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [FAIL] action NULL: {n}건")
            errors += 1
        else:
            print(f"  [PASS] action NULL: 0건")
    
        # 2. date 빈값 검사
        c.execute("SELECT COUNT(*) FROM trade_log WHERE date IS NULL OR date = ''")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [FAIL] date NULL/empty: {n}건")
            errors += 1
        else:
            print(f"  [PASS] date NULL/empty: 0건")
    
        # 3. SELL profit 미계산 검사
        c.execute("""SELECT COUNT(*) FROM trade_log 
                     WHERE action='SELL' AND (profit IS NULL OR profit = 0) 
                     AND profit_pct IS NOT NULL AND profit_pct != 0""")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [FAIL] SELL profit 미계산: {n}건")
            errors += 1
        else:
            print(f"  [PASS] SELL profit 계산 완료")
    
        # 4. investment_type NULL (BUY/SELL만)
        c.execute("SELECT COUNT(*) FROM trade_log WHERE action IN ('BUY','SELL') AND investment_type IS NULL")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [WARN] investment_type NULL (BUY/SELL): {n}건")
            warnings += 1
        else:
            print(f"  [PASS] investment_type 정상")
    
        # 5. 유령 종목 (epoch 이후만 검사)
        epoch_filter = f"AND date >= '{epoch}'" if epoch else ""
        c.execute(f"""SELECT COUNT(DISTINCT tl.code) FROM (
            SELECT code, SUM(CASE WHEN action='BUY' THEN qty ELSE 0 END) as b,
                   SUM(CASE WHEN action='SELL' THEN qty ELSE 0 END) as s
            FROM trade_log WHERE action IN ('BUY','SELL') {epoch_filter}
            GROUP BY code HAVING b > s
        ) tl LEFT JOIN current_holdings ch ON tl.code = ch.code
        WHERE ch.code IS NULL""")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [WARN] 유령 종목 (epoch후, BUY>SELL, 미보유): {n}개")
            if verbose:
                c.execute(f"""SELECT tl.code, tl.b - tl.s as diff FROM (
                    SELECT code, SUM(CASE WHEN action='BUY' THEN qty ELSE 0 END) as b,
                           SUM(CASE WHEN action='SELL' THEN qty ELSE 0 END) as s
                    FROM trade_log WHERE action IN ('BUY','SELL') {epoch_filter}
                    GROUP BY code HAVING b > s
                ) tl LEFT JOIN current_holdings ch ON tl.code = ch.code
                WHERE ch.code IS NULL""")
                for r in c.fetchall():
                    # 부분체결 중복 여부 확인
                    c.execute(f"""SELECT COUNT(*) FROM (
                        SELECT date, price, COUNT(*) as cnt
                        FROM trade_log WHERE code=? AND action='BUY' {epoch_filter}
                        GROUP BY date, price HAVING cnt > 2
                    )""", (r[0],))
                    dup = c.fetchone()[0]
                    note = " (부분체결 중복 의심)" if dup > 0 else ""
                    print(f"         {r[0]} 잔여={r[1]}{note}")
            warnings += 1
        else:
            print(f"  [PASS] 유령 종목 없음 (epoch후)")
    
        # 6. trade_log 중복 검사
        c.execute("""SELECT COUNT(*) FROM (
            SELECT date, code, action, price, qty, COUNT(*) as cnt
            FROM trade_log WHERE action IN ('BUY','SELL')
            GROUP BY date, code, action, price, qty HAVING cnt > 1
        )""")
        n = c.fetchone()[0]
        if n > 0:
            print(f"  [WARN] 중복 의심 거래: {n}그룹")
            warnings += 1
        else:
            print(f"  [PASS] 중복 거래 없음")
    
        # 7. 총 실현손익 (epoch 이후)
        if epoch:
            c.execute(f"SELECT SUM(profit) FROM trade_log WHERE action='SELL' AND profit IS NOT NULL AND date >= '{epoch}'")
            total_epoch = c.fetchone()[0] or 0
            print(f"\n  [INFO] 실현손익 (epoch후): {total_epoch:,.0f}원")
        c.execute("SELECT SUM(profit) FROM trade_log WHERE action='SELL' AND profit IS NOT NULL")
        total = c.fetchone()[0] or 0
        print(f"  [INFO] 실현손익 (전체): {total:,.0f}원")
    
        # 8. trade_log 통계
        c.execute("SELECT COUNT(*) FROM trade_log")
        total_rows = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM trade_log WHERE action='BUY'")
        buys = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM trade_log WHERE action='SELL'")
        sells = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM current_holdings")
        holdings = c.fetchone()[0]
        print(f"  [INFO] trade_log: {total_rows}건 (BUY={buys}, SELL={sells}), 보유={holdings}종목")
    
    
        print(f"\n{'=' * 60}")
        if errors == 0:
            print(f"  [OK] 검사 완료: 에러 {errors}, 경고 {warnings}")
        else:
            print(f"  [FAIL] 검사 완료: 에러 {errors}, 경고 {warnings}")
        print(f"{'=' * 60}")
    
        return errors

    finally:
        conn.close()
if __name__ == '__main__':
    errors = check_integrity(verbose='--verbose' in sys.argv)
    sys.exit(1 if errors > 0 else 0)
