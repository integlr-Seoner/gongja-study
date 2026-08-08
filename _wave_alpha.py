# -*- coding: utf-8 -*-
"""ⓒ 파동↔α — 거래대금이 저자 적정거래대금(절대값)을 상향돌파하는 에피소드 수 vs 저자 파동 수"""
import io, re, sys, json
import numpy as np
import statistics as st
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 적정거래대금(억): 1부 노트 추출 + 2부 하드코딩(G943)
fp = r"D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md"
lines = io.open(fp, encoding="utf-8").readlines()
hdr = re.compile(r'^## G(\d+)\.\s*\[사례(\d+)\s+([^\]\s]+)')
adjpat = re.compile(r'적정거래대금[^\d]{0,8}([\d,]+)\s*(?:~\s*([\d,]+))?\s*억')
def n_(s): return int(s.replace(',', ''))
cases={}; cur=None
for l in lines:
    m=hdr.match(l)
    if m:
        k=int(m.group(2))
        if k not in cases: cases[k]={'name':m.group(3),'lines':[]}
        cur=k
    if cur is not None: cases[cur]['lines'].append(l)
ADJ={}
for k in cases:
    for l in cases[k]['lines']:
        mm=adjpat.search(l)
        if mm:
            lo=n_(mm.group(1)); hi=n_(mm.group(2)) if mm.group(2) else None
            ADJ[cases[k]['name']]=(lo+hi)//2 if hi else lo; break
ADJ.update({'맥스트':4000,'네오위즈':2200,'삼아알미늄':1350,'제주반도체':2100,'KEC':1800,
    '비트나인':1300,'FSN':1000,'램테크놀러지':1800,'이노뎁':1200,'와이제이엠게임즈':1700,
    '인성정보':800,'이씨에스':1000,'이수앱지스':2000,'엑세스바이오':3600})

# 저자 파동 수
waves={}
for part in ['1부','2부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        if any(name.startswith(k) for k in ADJ):
            w=sum(1 for t,d,v in recs if t=='WAVE'); waves[name]=w+1

data=json.load(open(r'D:\StockAnalyst\book_extracts\_krx_90v2.json',encoding='utf-8'))
dates=sorted(data.keys())

def episodes(name, adj, merge):
    ser=[(d,data[d][name][5]/1e8) for d in dates if name in data.get(d,{}) and data[d][name][5]]
    above=[i for i,(d,v) in enumerate(ser) if v>=adj]
    if not above: return 0
    ep=1
    for a,b in zip(above,above[1:]):
        if b-a>merge: ep+=1
    return ep

for MERGE in (5,10,20):
    pairs=[]
    for name,w in waves.items():
        key=next((k for k in ADJ if name.startswith(k)),None)
        ep=episodes(name, ADJ[key], MERGE)
        pairs.append((name,w,ep))
    a=np.array([p[1] for p in pairs]); c=np.array([p[2] for p in pairs])
    exact=sum(1 for p in pairs if p[1]==p[2]); w1=sum(1 for p in pairs if abs(p[1]-p[2])<=1)
    print('=== MERGE %dbd ===  종목 %d | 저자파동 평균 %.2f | α에피소드 평균 %.2f | r=%.3f | 정확 %d(%.0f%%) | ±1 %d(%.0f%%)'
          % (MERGE,len(pairs),a.mean(),c.mean(),np.corrcoef(a,c)[0,1],exact,100*exact/len(pairs),w1,100*w1/len(pairs)))
# 상세(MERGE=10)
print('\n[MERGE=10 상세]')
for name,w in waves.items():
    key=next((k for k in ADJ if name.startswith(k)),None)
    ep=episodes(name,ADJ[key],10)
    mark='✓' if abs(w-ep)<=1 else ' '
    print('  %s %-14s 저자 %d / α에피소드 %d (적정 %d억)' % (mark,name[:14],w,ep,ADJ[key]))
