# -*- coding: utf-8 -*-
# 배치 24(G2031~G2041) 핸드오버 동기화 — API 오류로 Claude Code 미실행분
# 0건 치환이 하나라도 있으면 아무것도 쓰지 않고 중단
import io, sys

P = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'

SUBS = [
    ('G1988~G2030', 'G1988~G2041'),
    ('headers 1903', 'headers 1914'),
    ('last G 2030', 'last G 2041'),
    (r'page_041.jpg', r'page_051.jpg'),
    ('S02 40/113p', 'S02 50/113p'),
    ('S02 73p', 'S02 63p'),
    ('G2031부터', 'G2042부터'),
]

EXPECT = {  # 문자열: 기대 건수
    'G1988~G2030': 1, 'headers 1903': 3, 'last G 2030': 2,
    'page_041.jpg': 2, 'S02 40/113p': 1, 'G2031부터': None,
}

t = io.open(P, encoding='utf-8').read()
before = len(t)
fail = 0
for b, a in SUBS:
    c = t.count(b)
    exp = EXPECT.get(b)
    ok = c >= 1 and (exp is None or c == exp)
    print('%s %-16s %d건%s' % ('OK' if ok else '!!', b, c,
                               '' if exp is None else ' (기대 %d)' % exp))
    if c == 0:
        fail += 1
if fail:
    print('\n%d건이 0건 — 아무것도 쓰지 않고 중단' % fail)
    sys.exit(1)
for b, a in SUBS:
    t = t.replace(b, a)
io.open(P, 'w', encoding='utf-8', newline='').write(t)
print('\n적용: %d -> %d chars' % (before, len(t)))
