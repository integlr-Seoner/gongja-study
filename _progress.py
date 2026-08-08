# -*- coding: utf-8 -*-
import io, re
N = r'D:\StockAnalyst\book_extracts\학습노트\11_단타매매_정독.md'
L = io.open(N, encoding='utf-8').read().split('\n')

print('=== S05~S10 헤더 실측 ===')
for tag in ['S05', 'S06', 'S07', 'S08', 'S09', 'S10']:
    gs = []
    for l in L:
        m = re.match(r'^## G(\d+)\.', l)
        if m and tag in l[:60]:
            gs.append(int(m.group(1)))
    if gs:
        print('  %s : G%d ~ G%d  (%d개)' % (tag, min(gs), max(gs), len(gs)))
    else:
        print('  %s : 없음' % tag)

print()
print('=== 헤더 표기 형식 표본 (S05 첫 헤더) ===')
for l in L:
    m = re.match(r'^## G(\d+)\.', l)
    if m and 'S05' in l[:60]:
        print('  ' + l.strip()[:100])
        break

print()
print('=== 내 _progress.py 패턴이 놓친 이유 ===')
pat = re.compile(r'\[(S0\d[^\]]*)\]')
hit = sum(1 for l in L if re.match(r'^## G\d+\.', l) and pat.search(l))
print('  대괄호 [S0x] 형식 헤더 : %d개' % hit)
hit2 = sum(1 for l in L if re.match(r'^## G\d+\.', l) and re.search(r'S0[5-9]|S10', l[:60]))
print('  S05~S10 헤더(형식 무관) : %d개' % hit2)
