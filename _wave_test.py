# -*- coding: utf-8 -*-
"""ⓕ 파동 독립 검정 — 거래대금 급증 클러스터 수 vs 저자 파동 수(WAVE 구분자+1)"""
import io, sys, json
import numpy as np
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.load(open(r'D:\StockAnalyst\book_extracts\_krx_90v2.json', encoding='utf-8'))
dates_sorted = sorted(data.keys())
LOOK=40; THR=10; MERGE=10   # 급증일 간격 10영업일 이하면 같은 클러스터

author={}; 
for part in ['1부','2부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        waves=sum(1 for t,d,v in recs if t=='WAVE')
        ds=[d for t,d,v in recs if t=='REC']
        if ds: author[name]=waves+1   # 구분자 +1 = 파동 수

pairs=[]
for name in author:
    ser=[(d, data[d][name][5]) for d in dates_sorted if name in data.get(d,{}) and data[d][name][5]]
    vals=[v for _,v in ser]
    flagidx=[]
    for i in range(LOOK,len(ser)):
        med=np.median(vals[i-LOOK:i])
        if med>0 and ser[i][1]/med>=THR: flagidx.append(i)
    # 클러스터링(인덱스 간격 <= MERGE 병합)
    clusters=0
    if flagidx:
        clusters=1
        for a,b in zip(flagidx, flagidx[1:]):
            if b-a>MERGE: clusters+=1
    pairs.append((name, author[name], clusters))

a=np.array([p[1] for p in pairs]); c=np.array([p[2] for p in pairs])
print('종목수 %d | 저자 파동 합 %d | 급증 클러스터 합 %d' % (len(pairs), a.sum(), c.sum()))
print('저자 파동 평균 %.2f | 클러스터 평균 %.2f' % (a.mean(), c.mean()))
print('상관계수 r = %.3f' % np.corrcoef(a,c)[0,1])
exact=sum(1 for p in pairs if p[1]==p[2]); within1=sum(1 for p in pairs if abs(p[1]-p[2])<=1)
print('정확 일치 %d/%d (%.0f%%) | ±1 이내 %d/%d (%.0f%%)'
      % (exact,len(pairs),100*exact/len(pairs), within1,len(pairs),100*within1/len(pairs)))
print('\n[클러스터 > 저자파동 상위 5]')
for p in sorted(pairs,key=lambda x:x[2]-x[1],reverse=True)[:5]:
    print('  %-16s 저자 %d / 클러스터 %d' % p)
