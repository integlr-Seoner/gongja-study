"""_v_61_market_state_honest.py — 시장 상태 데이터 근거 확인

Seoner 지적: "지금 한국 시장이 위험하다는 근거는?"
→ 이전 답변의 'BULL 말기 상투' 주장에 대한 데이터 근거 찾기.

실측 순서:
  1. daily_journal 의 macro_score / macro_regime (auto_trader 가 실제 본 시장)
  2. KOSPI / KOSDAQ 최근 30일 변동 (index_daily)
  3. VIX / FGI 추이
  4. 4/22 의 매수 차단 필터 비율 (기술 게이트가 실제로 비정상적인가?)
"""
import sqlite3
DB = r'D:\StockAnalyst\trading_system.db'
c = sqlite3.connect(DB, timeout=30)
cur = c.cursor()

# 1) daily_journal: 4/2~4/22 매일 시장 상태
print('=' * 80)
print('[1] daily_journal 기록 — auto_trader 가 본 시장 상태')
print('=' * 80)
rows = cur.execute("""
    SELECT journal_date, macro_score, macro_regime, market_vix, market_fgi,
           kospi_change, kosdaq_change, buy_count, sell_count
    FROM daily_journal
    WHERE journal_date >= '2026-04-02'
    ORDER BY journal_date
""").fetchall()
print(f'  {"date":<12} {"macro":<7} {"regime":<10} {"VIX":<6} {"FGI":<5} '
      f'{"KOSPI":<8} {"KOSDAQ":<8} {"BUY":<4} {"SELL":<4}')
for r in rows:
    print(f'  {r[0]:<12} {r[1]!s:<7} {r[2]!s:<10} {r[3]!s:<6} {r[4]!s:<5} '
          f'{r[5]!s:<8} {r[6]!s:<8} {r[7]:<4} {r[8]:<4}')

# 2) KOSPI / KOSDAQ 인덱스 추이
print('\n' + '=' * 80)
print('[2] KOSPI / KOSDAQ 최근 추이 (index_daily)')
print('=' * 80)
try:
    cols = cur.execute("PRAGMA table_info(index_daily)").fetchall()
    col_names = [c[1] for c in cols]
    print(f'  컬럼: {col_names}')
    
    # KOSPI 찾기
    distinct_codes = cur.execute("SELECT DISTINCT code FROM index_daily").fetchall()
    print(f'  인덱스 종류: {[r[0] for r in distinct_codes]}')
    
    for idx_code in ['KOSPI', 'KOSDAQ']:
        rows = cur.execute(f"""
            SELECT date, open, high, low, close, change_pct FROM index_daily
            WHERE code = ? AND date >= '20260301'
            ORDER BY date
        """, (idx_code,)).fetchall()
        if not rows:
            print(f'\n  {idx_code}: 데이터 없음')
            continue
        first = rows[0][4]; last = rows[-1][4]
        chg = (last / first - 1) * 100 if first > 0 else 0
        high_all = max(r[2] for r in rows)
        low_all = min(r[3] for r in rows)
        print(f'\n  [{idx_code}]  {rows[0][0]} {first:.1f} → {rows[-1][0]} {last:.1f} ({chg:+.2f}%)')
        print(f'   고점 {high_all:.1f} / 저점 {low_all:.1f}')
        print(f'   고점 대비 현재: {(last/high_all-1)*100:+.2f}%')
        print(f'   최근 10일:')
        for r in rows[-10:]:
            print(f'     {r[0]}: open={r[1]:.1f} close={r[4]:.1f} ({r[5]:+.2f}%)')
        continue  # 아래 기존 로직 스킵
        rows = []
        if rows:
            first = rows[0][1]; last = rows[-1][1]
            chg = (last / first - 1) * 100 if first > 0 else 0
            print(f'\n  {idx_code}: {rows[0][0]} {first} → {rows[-1][0]} {last} ({chg:+.2f}%)')
            # 최근 5일
            for r in rows[-5:]:
                print(f'    {r[0]} close={r[1]}')
except Exception as e:
    print(f'  오류: {e}')

c.close()
