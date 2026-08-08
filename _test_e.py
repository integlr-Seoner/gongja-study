# -*- coding: utf-8 -*-
"""ⓔ 편입일 탐지 검정 — 44차 G966: '편입일 = 거래대금 평소의 10배 + 재료 최초 등장'"""
import io, sys, json
from datetime import datetime, timedelta
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statistics as st

D = json.load(open(r'D:\StockAnalyst\book_extracts\_krx_90v2.json', encoding='utf-8'))
LOOKBACK = 40

def bdays_before(d0, n):
    out, cur = [], d0 - timedelta(days=1)
    while len(out) < n:
        if cur.weekday() < 5: out.append(cur.strftime('%Y%m%d'))
        cur -= timedelta(days=1)
    return out

rows = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        key = name
        ds = sorted(d for t, d, v in recs if t == 'REC')
        if not ds: continue
        d0 = ds[0]
        prev = [D[x][key][5] for x in bdays_before(d0, LOOKBACK)
                if x in D and key in D[x] and D[x][key][5] > 0]
        cur = D.get(d0.strftime('%Y%m%d'), {}).get(key)
        if len(prev) < 15 or cur is None: continue
        base = st.median(prev)                       # 평소 거래대금
        ratio = cur[5] / base if base > 0 else 0
        rows.append((ratio, part, key, d0.date(), base/1e8, cur[5]/1e8, cur[4]))

rows.sort(reverse=True)
print('대상 %d종 (룩백 %d영업일 중 거래 15일 이상)' % (len(rows), LOOKBACK))
rs = [r[0] for r in rows]
print('★첫 재료일 거래대금 / 평소(중앙값) 배수:')
print('   min=%.1f  Q1=%.1f  중앙=%.1f  Q3=%.1f  max=%.0f  평균=%.1f'
      % (min(rs), st.quantiles(rs,n=4)[0], st.median(rs), st.quantiles(rs,n=4)[2], max(rs), st.mean(rs)))
for th in (2, 3, 5, 10, 20):
    n = sum(1 for r in rs if r >= th)
    print('   %2d배 이상: %2d/%d = %3.0f%%' % (th, n, len(rs), 100*n/len(rs)))
print()
print('%-18s %-5s %-11s %8s %8s %7s %s' % ('종목','부','첫재료일','평소(억)','당일(억)','배수','등락률'))
print('-' * 84)
for r, part, k, d, b, c, p in rows[:12]:
    print('%-18s %-5s %-11s %8.0f %8.0f %6.1f배 %+6.1f%%' % (k, part, d, b, c, r, p))
print('   ... (중략) ...')
for r, part, k, d, b, c, p in rows[-8:]:
    print('%-18s %-5s %-11s %8.0f %8.0f %6.1f배 %+6.1f%%' % (k, part, d, b, c, r, p))
