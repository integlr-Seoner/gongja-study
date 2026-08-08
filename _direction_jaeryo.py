# -*- coding: utf-8 -*-
"""재료 텍스트의 방향성 검증: '강세/급등' vs '급락/하락' vs 중립"""
import os, sys, io, re
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

UP = ['강세', '급등', '상승', '상한가', '오를', '훈풍', '초강세', '화제', '주목', '기대']
DOWN = ['급락', '하락', '폭락', '약세', '하한가', '내림', '떨어']

tot = {'UP': 0, 'DOWN': 0, 'BOTH': 0, 'NEUTRAL': 0, 'EMPTY': 0}
hits = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        for t, d, v in recs:
            if t != 'REC':
                continue
            s = ('' if v[1] is None else str(v[1])).strip()
            if s in ('', '-'):
                tot['EMPTY'] += 1; continue
            u = any(w in s for w in UP)
            dn = any(w in s for w in DOWN)
            if u and dn:
                tot['BOTH'] += 1; hits.append((part, name, d, v[0], s, 'BOTH'))
            elif dn:
                tot['DOWN'] += 1; hits.append((part, name, d, v[0], s, 'DOWN'))
            elif u:
                tot['UP'] += 1
            else:
                tot['NEUTRAL'] += 1; hits.append((part, name, d, v[0], s, 'NEUTRAL'))

print('전체 1,269건 분류:')
for k in ['UP', 'DOWN', 'BOTH', 'NEUTRAL', 'EMPTY']:
    print('  %-8s %5d건 (%.1f%%)' % (k, tot[k], 100 * tot[k] / 1269))
print()
print('★ DOWN / BOTH / NEUTRAL 전수 (%d건):' % len(hits))
for part, name, d, amt, s, kind in hits:
    print('  [%s] %-5s %-22s %s | %6s | %s' % (kind, part, name, d.strftime('%Y-%m-%d'), amt, s[:78]))
