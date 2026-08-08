"""_v_63_fixed_query_dryrun.py — 수정된 쿼리의 4/22 결과 미리보기

수정안:
  1. scanned_targets_v2 최신 1건만 매칭 (중복 제거)
  2. 종가배팅으로 분류되는 종목은 cb_cond 1개 이상 통과 필수
"""
import sqlite3
DB = r'D:\StockAnalyst\trading_system.db'
c = sqlite3.connect(DB, timeout=30)
cur = c.cursor()

TYPE_LIMITS = {'종가배팅': 5, '스윙': 5, '중장기': 3}

query = """
WITH sv_latest AS (
    SELECT code,
           MAX(cb_cond1) AS cb_cond1,
           MAX(cb_cond2) AS cb_cond2,
           MAX(cb_cond3) AS cb_cond3
    FROM scanned_targets_v2
    WHERE created_at >= date('now', '-2 days')
    GROUP BY code
)
SELECT u.code, u.name,
       u.score_closing_a, u.score_swing_a, u.score_longterm_a,
       u.strategy_count, u.strategies,
       COALESCE(sv.cb_cond1,0), COALESCE(sv.cb_cond2,0), COALESCE(sv.cb_cond3,0)
FROM unified_rankings u
INNER JOIN sv_latest sv ON u.code = sv.code
WHERE u.date = ?
  AND u.strategy_count >= 2
  AND NOT (
      u.score_closing_a >= u.score_swing_a
      AND u.score_closing_a >= u.score_longterm_a
      AND COALESCE(sv.cb_cond1,0) = 0
      AND COALESCE(sv.cb_cond2,0) = 0
      AND COALESCE(sv.cb_cond3,0) = 0
  )
  AND NOT EXISTS (
      SELECT 1 FROM strategy_recommendations r
      WHERE r.code = u.code AND r.date = u.date AND r.bought = 1
  )
ORDER BY
    CASE
        WHEN u.score_closing_a >= u.score_swing_a AND u.score_closing_a >= u.score_longterm_a
            THEN u.score_closing_a
        WHEN u.score_swing_a >= u.score_longterm_a
            THEN u.score_swing_a
        ELSE u.score_longterm_a
    END DESC
LIMIT 50
"""

rows = cur.execute(query, ('20260422',)).fetchall()
print(f'수정 쿼리 결과: {len(rows)}건 (중복 제거 확인)')
print()
print(f'{"code":<8} {"name":<16} {"type":<8} {"점수":<8} {"cb":<4}')
print('-' * 60)

type_counts = {'종가배팅': 0, '스윙': 0, '중장기': 0}
picked = []

for r in rows:
    code, name, cs, ss, ls, sc, strats, c1, c2, c3 = r
    cs = cs or 0; ss = ss or 0; ls = ls or 0
    scores = {'종가배팅': cs, '스윙': ss, '중장기': ls}
    t = max(scores, key=scores.get)
    best = scores[t]
    cb = 'O' if (c1 or c2 or c3) else 'X'
    
    if type_counts[t] < TYPE_LIMITS[t]:
        picked.append((code, name, t, best, cb))
        type_counts[t] += 1

print(f'상위 {len(picked)}개 후보 (타입 한도 적용):')
for code, name, t, score, cb in picked:
    print(f'  {code} {name:<14} {t:<10} {score:>6.2f}  cb={cb}')

print()
print(f'타입별: 종가 {type_counts["종가배팅"]}, 스윙 {type_counts["스윙"]}, 중장기 {type_counts["중장기"]}')

# cb 미통과 비율 확인 (수정 후)
cb_fail = sum(1 for x in picked if x[4] == 'X')
print(f'cb 미통과 후보: {cb_fail}개 (수정 전: 5개)')

c.close()
