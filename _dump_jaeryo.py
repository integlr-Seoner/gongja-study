# -*- coding: utf-8 -*-
"""재료 엑셀 종목별 원문 덤프 (정독용)"""
import os, sys, io
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

part = sys.argv[1] if len(sys.argv) > 1 else '1부'
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 1
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 5

title, stocks = parse(part)
for idx, (name, recs) in enumerate(stocks, 1):
    if not (lo <= idx <= hi):
        continue
    vals = [v[0] for t, d, v in recs if t == 'REC' and isinstance(v[0], (int, float))]
    print('=' * 96)
    print('#%02d %s   | 레코드 %d건 | 거래대금 %s~%s억'
          % (idx, name, len(vals), min(vals) if vals else '-', max(vals) if vals else '-'))
    print('-' * 96)
    for t, d, v in recs:
        if t == 'WAVE':
            print('    ---- %s ----' % d)
        else:
            amt = v[0] if v[0] is not None else ''
            news = v[1] if v[1] is not None else ''
            print('    %s | %6s | %s' % (d.strftime('%Y-%m-%d'), amt, news))
