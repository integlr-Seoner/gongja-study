# -*- coding: utf-8 -*-
import io, re
h = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'
t = io.open(h, encoding='utf-8').read()
L = t.split('\n')
print('chars: %d / lines: %d' % (len(t), len(L)))
print()
print('=== 핸드오버가 주장하는 상태 ===')
for pat in ['G-spine = \\*\\*G128~G(\\d+) / headers (\\d+)',
            'last G (\\d+)\\*\\* 확인',
            'page_0(\\d\\d)\\.jpg` 부터 10장 단위, \\*\\*G(\\d+)부터',
            '다음 시작점 = `S02_갭하락_흐름예시\\\\page_0(\\d\\d)\\.jpg`, G(\\d+)부터',
            'S02 (\\d+)/113p',
            'S02 (\\d+)p\\*\\*\\(S01 완독\\)']:
    m = re.search(pat, t)
    print('  %-52s %s' % (pat[:50], m.groups() if m else '없음'))
print()
print('=== 실제 상태 ===')
print('  노트 마지막 G = G2019 / headers 1892 / S02 30/113p')
print()
print('=== 판정 ===')
ok = ('G128~G2019' in t) and ('headers 1892' in t) and ('page_031' in t) and ('G2020' in t)
print('  핸드오버 최신' if ok else '  ⚠️ 핸드오버가 뒤처짐 — 다음 세션이 중복/누락 위험')
