# -*- coding: utf-8 -*-
import os, sys, io, re
import openpyxl
from datetime import datetime

D = r'D:\StockAnalyst\금융공자_가이드북\차트매매\일봉 차트 수급 추적 자료집'

def parse(part):
    p = os.path.join(D, '일봉 차트 수급 추적 재료 자료집 - %s.xlsx' % part)
    wb = openpyxl.load_workbook(p, data_only=True)
    ws = wb.worksheets[0]
    stocks = []
    for row in ws.iter_rows(values_only=True):
        vals = list(row) + [None] * (3 - len(row))
        a, b, c = vals[0], vals[1], vals[2]
        s = '' if a is None else str(a).strip()
        if s.startswith('종목명'):
            stocks.append((s.replace('종목명', '').lstrip(' :').strip(), []))
            continue
        if isinstance(a, datetime):
            if stocks:
                stocks[-1][1].append(('REC', a, (b, c)))
            continue
        # 파동 구분자: A열이 날짜가 아니고, A열 자체가 '~차 상승 마무리' 꼴일 때만
        if re.match(r'^\s*\d+\s*차\s*상승\s*마무리\s*$', s):
            if stocks:
                stocks[-1][1].append(('WAVE', s, None))
    wb.close()
    return ws.title, stocks

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    for part in ['1부', '2부', '3부']:
        title, stocks = parse(part)
        nrec = sum(1 for _, rs in stocks for t, _, _ in rs if t == 'REC')
        nwave = sum(1 for _, rs in stocks for t, _, _ in rs if t == 'WAVE')
        ds = [d for _, rs in stocks for t, d, _ in rs if t == 'REC']
        print('=' * 74)
        print('[%s] sheet=%r | stocks=%d | records=%d | wave-sep=%d'
              % (part, title, len(stocks), nrec, nwave))
        if ds:
            print('  period: %s ~ %s' % (min(ds).date(), max(ds).date()))
        print('  stocks: ' + ' / '.join(n for n, _ in stocks))
