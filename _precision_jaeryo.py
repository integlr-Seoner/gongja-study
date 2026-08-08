# -*- coding: utf-8 -*-
"""ⓕ 편입일/재료 precision — 급증일(거래대금≥N배 직전40bd중앙값)이 재료일인가?"""
import io, sys, json
import numpy as np
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.load(open(r'D:\StockAnalyst\book_extracts\_krx_90v2.json', encoding='utf-8'))
dates_sorted = sorted(data.keys())

# 종목별 재료일(엑셀) + 첫 재료일
mat={}   # name -> set of 'YYYYMMDD'
first={} # name -> first 'YYYYMMDD'
for part in ['1부','2부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        ds=sorted(d for t,d,v in recs if t=='REC')
        if not ds: continue
        s=set(d.strftime('%Y%m%d') for d in ds)
        mat[name]=s; first[name]=ds[0].strftime('%Y%m%d')

LOOK=40
def run(thr):
    tot_flag=0; flag_mat=0; flag_first=0
    tot_first=0; first_flagged=0   # recall 재확인
    per=[]
    for name in mat:
        # 이 종목의 (date,value) 시계열 (캐시에 존재하는 날만)
        ser=[(d, data[d][name][5]) for d in dates_sorted if name in data.get(d,{}) and data[d][name][5]]
        vals=[v for _,v in ser]
        nflag=0; nmat=0
        for i,(d,v) in enumerate(ser):
            if i<LOOK: continue
            med=np.median(vals[i-LOOK:i])
            if med<=0: continue
            if v/med>=thr:
                nflag+=1; tot_flag+=1
                if d in mat[name]:
                    nmat+=1; flag_mat+=1
                    if d==first[name]: flag_first+=1
        per.append((name,nflag,nmat))
        # recall: 첫 재료일이 flag 되는가
        f=first[name]
        idx=[i for i,(d,_) in enumerate(ser) if d==f]
        if idx and idx[0]>=LOOK:
            tot_first+=1
            i=idx[0]; med=np.median(vals[i-LOOK:i])
            if med>0 and ser[i][1]/med>=thr: first_flagged+=1
    print('=== 임계 %gx ===' % thr)
    print('  급증일 총 %d | 재료일 %d (%.1f%%) | 첫재료일 %d (%.1f%%)'
          % (tot_flag, flag_mat, 100*flag_mat/tot_flag, flag_first, 100*flag_first/tot_flag))
    print('  [대조 recall] 첫재료일 %d종 중 flag %d (%.1f%%)'
          % (tot_first, first_flagged, 100*first_flagged/tot_first))
    return per

for thr in (5,10,20):
    per=run(thr)
    print()
