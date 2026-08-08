# -*- coding: utf-8 -*-
"""저자 제시 적정거래대금이 '재료 발생일 거래대금' 분포의 몇 분위수인지 산출"""
import os, sys, io
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statistics as st

# 정독 노트 G-spine 근거. 밴드 제시분은 (하한, 상한) 튜플.
ADJ = {
    '맥스트': 4000, '네오위즈': 2200, '삼아알미늄': (1300, 1400),
    '제주반도체': 2100, 'KEC': 1800, '비트나인': 1300, 'FSN': 1000,
    '램테크놀러지': 1800, '이노뎁': 1200, '와이제이엠게임즈': 1700,
    '인성정보': 800, '이씨에스': 1000, '이수앱지스': 2000, '엑세스바이오': 3600,
}

def pct_rank(vals, x):
    """x보다 작거나 같은 값의 비율 (0~1)"""
    return sum(1 for v in vals if v <= x) / len(vals)

title, stocks = parse('2부')
rows = []
print('%-22s %4s %7s %7s %7s %7s %7s | %8s %7s %7s' %
      ('종목', 'n', 'min', 'Q1', 'med', 'Q3', 'max', '적정', '분위수', '적정/med'))
print('-' * 104)
for name, recs in stocks:
    vals = sorted(v[0] for t, d, v in recs if t == 'REC' and isinstance(v[0], (int, float)))
    key = next((k for k in ADJ if name.startswith(k)), None)
    if not vals or key is None:
        continue
    a = ADJ[key]
    a_mid = sum(a) / 2 if isinstance(a, tuple) else a
    q = st.quantiles(vals, n=4) if len(vals) >= 4 else [vals[0], st.median(vals), vals[-1]]
    pr = pct_rank(vals, a_mid)
    ratio = a_mid / st.median(vals)
    rows.append((pr, ratio, name))
    print('%-22s %4d %7d %7.0f %7.0f %7.0f %7d | %8s %6.0f%% %7.2f' %
          (name, len(vals), vals[0], q[0], st.median(vals), q[2], vals[-1],
           ('%d~%d' % a) if isinstance(a, tuple) else a, pr * 100, ratio))

print('-' * 104)
prs = [r[0] for r in rows]; rs = [r[1] for r in rows]
print('분위수  : n=%d  min=%.0f%%  med=%.0f%%  max=%.0f%%  평균=%.0f%%'
      % (len(prs), min(prs)*100, st.median(prs)*100, max(prs)*100, st.mean(prs)*100))
print('적정/med: min=%.2f  med=%.2f  max=%.2f  평균=%.2f'
      % (min(rs), st.median(rs), max(rs), st.mean(rs)))
