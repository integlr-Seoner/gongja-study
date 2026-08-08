# -*- coding: utf-8 -*-
# 한도 중단 시점 핸드오버 동기화 — 배치 22(G2009~G2019) 반영
# 0건 치환이 하나라도 있으면 아무것도 쓰지 않고 중단
import io, sys

P = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'

SUBS = [
    ('+ ★**S02 갭하락 흐름예시 p.1~20 완료(G1988~G2008)**',
     '+ ★**S02 갭하락 흐름예시 p.1~30 완료(G1988~G2019)**'),
    ('G-spine = **G128~G2008 / headers 1881 무결**',
     'G-spine = **G128~G2019 / headers 1892 무결**'),
    ('`OK` / **headers 1881 / last G 2008** 확인',
     '`OK` / **headers 1892 / last G 2019** 확인'),
    (r'`S02_갭하락_흐름예시\page_021.jpg` 부터 10장 단위, **G2009부터** append',
     r'`S02_갭하락_흐름예시\page_031.jpg` 부터 10장 단위, **G2020부터** append'),
    ('잔여 = 4-1권 **54p** + 자료집 **S02 93p**(S01 완독)',
     '잔여 = 4-1권 **54p** + 자료집 **S02 83p**(S01 완독)'),
    ('(S01 26/26p ✅완독 → S02 20/113p)',
     '(S01 26/26p ✅완독 → S02 30/113p)'),
    (r'''**다음 시작점 = `S02_갭하락_흐름예시\page_021.jpg`, G2009부터.**''',
     r'''⚠️★★★★★**[세션 중단 — Max 5x 한도 도달, 2026-07-27]** 배치 22(G2009~G2019) **노트 append·spine 검증까지 완료**된 상태에서 한도로 중단됨. 핸드오버는 웹 세션에서 동기화함(Claude Code 미수행). ★**중간 파일 `_append_log\_append_g2009.md` 보존됨** — 재개 시 **재작성 불필요**. ★**추가 사용(extra usage) 꺼짐 → 과금 없음.** ★재개 첫 행동 = `python _check_gspine.py` 로 **headers 1892 / last G 2019** 확인 후 아래 시작점부터 진행. **다음 시작점 = `S02_갭하락_흐름예시\page_031.jpg`, G2020부터.**'''),
]

t = io.open(P, encoding='utf-8').read()
before_len = len(t)
fail = 0
for i, (b, a) in enumerate(SUBS, 1):
    c = t.count(b)
    print('%s #%d  %d건  %s' % ('OK' if c == 1 else '!!', i, c, b[:46].replace('\n', ' ')))
    if c != 1:
        fail += 1
if fail:
    print('\n%d건 불일치 — 아무것도 쓰지 않고 중단' % fail)
    sys.exit(1)
for b, a in SUBS:
    t = t.replace(b, a)
io.open(P, 'w', encoding='utf-8', newline='').write(t)
print('\n적용 완료: %d → %d chars' % (before_len, len(t)))
