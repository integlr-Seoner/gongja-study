# -*- coding: utf-8 -*-
"""'마무리'가 A열이 아닌 곳에 있는 행 전수 조사"""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import openpyxl
from datetime import datetime

D = r'D:\StockAnalyst\금융공자_가이드북\차트매매\일봉 차트 수급 추적 자료집'
for part in ['1부', '2부', '3부']:
    p = os.path.join(D, '일봉 차트 수급 추적 재료 자료집 - %s.xlsx' % part)
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb.worksheets[0]
    print('=' * 80)
    print('[%s]' % part)
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        vals = list(row) + [None] * (3 - len(row))
        a, b, c = vals[0], vals[1], vals[2]
        sa = '' if a is None else str(a)
        sb = '' if b is None else str(b)
        sc = '' if c is None else str(c)
        if '마무리' in sb or '마무리' in sc:
            print('  ★행%d | A=%r | B=%r | C=%r' % (i, sa[:30], sb[:30], sc[:60]))
        elif '마무리' in sa and not sa.strip().endswith('마무리'):
            print('  ?행%d | A=%r' % (i, sa[:60]))
    wb.close()
