# -*- coding: utf-8 -*-
"""정독 노트에서 저자 제시 '적정거래대금' 언급을 전수 추출 (1부 G555~G761 / 2부 G763~G930)"""
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

P = r'D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md'
t = open(P, encoding='utf-8').read()

# G 항목 단위로 분할
blocks = re.split(r'(?m)^## (G\d+)\.', t)
items = []
for i in range(1, len(blocks), 2):
    items.append((blocks[i], blocks[i+1]))

pat = re.compile(r'적정\s*거래대금[^\n]{0,80}?([\d,]{3,6})\s*억')
pat2 = re.compile(r'([\d,]{3,6})\s*억[^\n]{0,30}?적정\s*거래대금')

hits = []
for gid, body in items:
    head = body.split('\n')[0][:70]
    found = set()
    for m in pat.finditer(body):
        found.add(m.group(1))
    for m in pat2.finditer(body):
        found.add(m.group(1))
    if found:
        hits.append((gid, head, sorted(found, key=lambda x: int(x.replace(',', '')))))

print('적정거래대금 수치가 언급된 G항목: %d개' % len(hits))
print('=' * 100)
for gid, head, vals in hits:
    print('%-6s %-14s | %s' % (gid, '/'.join(vals) + '억', head))
