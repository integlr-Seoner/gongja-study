# -*- coding: utf-8 -*-
"""거래대금 극소(<100억) 레코드 전수 — 쩜 상한가 가설 검정"""
import os, sys, io, re
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def waves_of(recs):
    ws, cur = [], []
    for t, d, v in recs:
        if t == 'WAVE':
            if cur: ws.append(cur); cur = []
        else:
            cur.append((d, v[0], ('' if v[1] is None else str(v[1])).strip()))
    if cur: ws.append(cur)
    return ws

TH = 100  # 억
rows = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        flat = [(d, v[0], ('' if v[1] is None else str(v[1])).strip())
                for t, d, v in recs if t == 'REC']
        for i, (d, a, s) in enumerate(flat):
            if not isinstance(a, (int, float)) or a >= TH: continue
            nxt = flat[i+1] if i+1 < len(flat) else None
            rows.append((a, part, name, d, s, nxt))

rows.sort()
print('거래대금 < %d억 레코드: %d건 / 전체 1,270건 (%.1f%%)' % (TH, len(rows), 100*len(rows)/1270))
print('=' * 100)
hit = 0
for a, part, name, d, s, nxt in rows:
    mark = ''
    if '상한가' in s: mark += '★상한가명시 '
    if '지속' in s: mark += '☆지속 '
    if '연일' in s: mark += '☆연일 '
    if mark: hit += 1
    print('%5d억 [%s] %-22s %s | %s' % (a, part, name, d.strftime('%Y-%m-%d'), mark))
    print('        재료: %s' % (s[:90] if s else '(없음)'))
    if nxt:
        print('        익일: %s | %s' % (nxt[1], (nxt[2][:70] if nxt[2] else '(없음)')))
print('=' * 100)
print('★"상한가"/"지속"/"연일" 어휘 포함: %d / %d건 (%.0f%%)' % (hit, len(rows), 100*hit/len(rows)))
