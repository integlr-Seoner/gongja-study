# -*- coding: utf-8 -*-
"""재료 엑셀 구조 통계: 재료 없는 레코드 / 파동 구조 / 재료 텍스트 유형"""
import os, sys, io, re
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statistics as st

for part in ['1부', '2부', '3부']:
    title, stocks = parse(part)
    tot = nonews = 0
    wave_counts = []
    amt_all = []
    label_like = 0          # "종목명, XXX 관련주" 형태 (뉴스가 아니라 라벨)
    per_stock_nonews = []
    for name, recs in stocks:
        n = nn = 0
        w = 0
        for t, d, v in recs:
            if t == 'WAVE':
                w += 1; continue
            n += 1; tot += 1
            amt, news = v
            if isinstance(amt, (int, float)):
                amt_all.append(amt)
            s = ('' if news is None else str(news)).strip()
            if s in ('', '-'):
                nn += 1; nonews += 1
            elif re.search(r'관련주\s*$', s):
                label_like += 1
        wave_counts.append(w)
        per_stock_nonews.append((nn / n if n else 0, name, nn, n))
    print('=' * 88)
    print('[%s] 레코드 %d건 | ★재료 없음("-") %d건 (%.1f%%) | "~관련주" 라벨형 %d건'
          % (part, tot, nonews, 100 * nonews / tot, label_like))
    print('  파동 구분자: 종목당 %s개 (합 %d)  | 0개인 종목 %d개'
          % ('/'.join(str(w) for w in wave_counts), sum(wave_counts),
             sum(1 for w in wave_counts if w == 0)))
    print('  거래대금(억): min=%d  Q1=%.0f  med=%.0f  Q3=%.0f  max=%d'
          % (min(amt_all), st.quantiles(amt_all, n=4)[0], st.median(amt_all),
             st.quantiles(amt_all, n=4)[2], max(amt_all)))
    per_stock_nonews.sort(reverse=True)
    print('  ★재료 없음 비율 상위 5:')
    for r, nm, nn, n in per_stock_nonews[:5]:
        print('     %-26s %2d/%2d = %.0f%%' % (nm, nn, n, r * 100))
