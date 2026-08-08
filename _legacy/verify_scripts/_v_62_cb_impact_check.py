"""_v_62_cb_impact_check.py — cb_cond 필터가 스윙/중장기 후보에 미치는 영향 실측

수정안: unified_rankings JOIN 에서 cb_cond 통과 종목만 허용
우려: 스윙/중장기 후보(cb_cond 무관한 투자 유형)까지 차단되지 않는지 확인

접근:
  4/22 auto_trader 후보 (종가 5 + 스윙 1 = 6개) 가 어떤 종목이었는지는 로그에 없음.
  대신 unified_rankings 에서 각 종목의 추정 investment_type (최고 점수 카테고리) 을 구하고,
  그 중 cb 미통과 종목이 스윙/중장기로 분류되는 비율 확인.
"""
import sqlite3
DB = r'D:\StockAnalyst\trading_system.db'
c = sqlite3.connect(DB, timeout=30)
cur = c.cursor()

# 4/22 unified_rankings 상위 50건 + cb_cond
rows = cur.execute("""
    SELECT u.code, u.name,
           u.score_closing_a, u.score_swing_a, u.score_longterm_a,
           u.strategy_count,
           sv.cb_cond1, sv.cb_cond2, sv.cb_cond3
    FROM unified_rankings u
    INNER JOIN scanned_targets_v2 sv
        ON u.code = sv.code
        AND sv.created_at >= date('now', '-3 days')
    WHERE u.date = '20260422'
      AND u.strategy_count >= 2
    ORDER BY
        CASE
            WHEN u.score_closing_a >= u.score_swing_a AND u.score_closing_a >= u.score_longterm_a
                THEN u.score_closing_a
            WHEN u.score_swing_a >= u.score_longterm_a
                THEN u.score_swing_a
            ELSE u.score_longterm_a
        END DESC
    LIMIT 50
""").fetchall()

print(f'4/22 unified_rankings 상위 {len(rows)} 종목 (cb_cond 미통과 표시)')
print()
print(f'{"code":<8} {"name":<16} {"추정type":<10} {"점수":<8} {"cb통과":<8}')
print('-' * 70)

inv_type_count = {'종가배팅': 0, '스윙': 0, '중장기': 0}
inv_type_cb_pass = {'종가배팅': 0, '스윙': 0, '중장기': 0}

TYPE_LIMITS = {'종가배팅': 5, '스윙': 5, '중장기': 3}
sim_counts = {'종가배팅': 0, '스윙': 0, '중장기': 0}
sim_picked = []  # (code, name, type)
sim_picked_cb_filtered = []

for r in rows:
    code, name, cs, ss, ls, sc, c1, c2, c3 = r
    cs = cs or 0; ss = ss or 0; ls = ls or 0
    scores = {'종가배팅': cs, '스윙': ss, '중장기': ls}
    t = max(scores, key=scores.get)
    best = scores[t]
    cb_pass = bool(c1 or c2 or c3)
    
    inv_type_count[t] += 1
    if cb_pass: inv_type_cb_pass[t] += 1
    
    mark = '✅' if cb_pass else '❌'
    print(f'{code:<8} {name:<16} {t:<10} {best:<8.2f} {mark:<8}')

    # 현재 로직 시뮬: 타입 한도 이내면 pick
    if sim_counts[t] < TYPE_LIMITS[t]:
        sim_picked.append((code, name, t, cb_pass))
        sim_counts[t] += 1

print()
print('[타입별 cb 통과 비율]')
for t, n in inv_type_count.items():
    p = inv_type_cb_pass[t]
    print(f'  {t}: 상위 {n}개 중 cb통과 {p}개 ({p/n*100 if n else 0:.0f}%)')

print()
print('[현재 로직이 뽑는 후보 13개]')
for code, name, t, cb in sim_picked:
    print(f'  {code} {name} ({t}) cb={"O" if cb else "X"}')

cb_filtered = [x for x in sim_picked if not x[3]]
print(f'\n이 중 cb 미통과: {len(cb_filtered)}개 → 전부 차단되어 매수 0건')

c.close()
