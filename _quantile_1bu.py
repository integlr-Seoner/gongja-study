# -*- coding: utf-8 -*-
"""ⓑ 1부 적정거래대금 → 재료일 거래대금 분위 매핑 + 2부 14종과 합산(표본 확대)"""
import io, re, sys
import statistics as st
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 1부 적정거래대금 노트 추출 (EDGC 등 '?' 표기 허용) ---
fp = r"D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md"
lines = io.open(fp, encoding="utf-8").readlines()
hdr = re.compile(r'^## G(\d+)\.\s*\[사례(\d+)\s+([^\]\s]+)')
adjpat = re.compile(r'적정거래대금[^\d]{0,8}([\d,]+)\s*(?:~\s*([\d,]+))?\s*억')
def num(s): return int(s.replace(',', ''))
cases = {}; cur=None
for l in lines:
    m=hdr.match(l)
    if m:
        n=int(m.group(2))
        if n not in cases: cases[n]={'name':m.group(3),'lines':[]}
        cur=n
    if cur is not None: cases[cur]['lines'].append(l)
ADJ1={}
for n in sorted(cases):
    for l in cases[n]['lines']:
        mm=adjpat.search(l)
        if mm:
            lo=num(mm.group(1)); hi=num(mm.group(2)) if mm.group(2) else None
            ADJ1[cases[n]['name']]=(lo+hi)//2 if hi else lo
            break

# --- 2부 저자 적정거래대금 (기존 G943 / _quantile_jaeryo.py) ---
ADJ2 = {'맥스트':4000,'네오위즈':2200,'삼아알미늄':1350,'제주반도체':2100,'KEC':1800,
        '비트나인':1300,'FSN':1000,'램테크놀러지':1800,'이노뎁':1200,'와이제이엠게임즈':1700,
        '인성정보':800,'이씨에스':1000,'이수앱지스':2000,'엑세스바이오':3600}

def pct_rank(vals,x): return sum(1 for v in vals if v<=x)/len(vals)

def eval_part(part, ADJ):
    _, stocks = parse(part); out=[]
    for name, recs in stocks:
        vals=sorted(v[0] for t,d,v in recs if t=='REC' and isinstance(v[0],(int,float)))
        key=next((k for k in ADJ if name.startswith(k)),None)
        if not vals or key is None: continue
        a=ADJ[key]; pr=pct_rank(vals,a); ratio=a/st.median(vals)
        out.append((name,len(vals),a,pr,ratio))
    return out

r1=eval_part('1부',ADJ1); r2=eval_part('2부',ADJ2)
print('=== 1부 (신규 추출) ===  매칭 %d종' % len(r1))
for name,n,a,pr,ra in sorted(r1,key=lambda x:x[3]):
    print('  %-14s n=%2d 적정=%5d 분위=%3.0f%% 적정/med=%.2f' % (name,n,a,pr*100,ra))
p1=[x[3] for x in r1]
print('  → 1부 분위: n=%d med=%.0f%% 평균=%.0f%%' % (len(p1),st.median(p1)*100,st.mean(p1)*100))
p2=[x[3] for x in r2]
print('=== 2부 (기존 14종) 분위: med=%.0f%% 평균=%.0f%%' % (st.median(p2)*100,st.mean(p2)*100))
pall=p1+p2
print('=== ★1+2부 통합 %d종 분위: min=%.0f%% med=%.0f%% max=%.0f%% 평균=%.0f%%'
      % (len(pall),min(pall)*100,st.median(pall)*100,max(pall)*100,st.mean(pall)*100))
ra_all=[x[4] for x in r1]+[x[4] for x in r2]
print('   적정/med: med=%.2f 평균=%.2f' % (st.median(ra_all),st.mean(ra_all)))
