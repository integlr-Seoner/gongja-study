# -*- coding: utf-8 -*-
# ⓐ 쩜상 제외 α(재료일 거래대금 40분위) 재산출 — 2부 쩜상 3종
import numpy as np, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

cases = {
 "폴라리스오피스(#11)": ([109,22,982,1049,822,305,1500,511,371,788,505,610], 22),
 "KEC(#21)":         ([193,23,1850,1015,834,1729,1558,6026,6042,3377,2436,5544,7059,2260,1999,4632,3913,3666,2235,3112,6671,1917], 23),
 "세종메디칼(#12)":    ([481,35,246,1394,753,2616,3388,2963,1208,1423,1537,1355,1807,2869,2804,5329,5436], 35),
}
def q40(v): return round(np.quantile(v, 0.4))
print("%-18s | n | a_full | a_excl쩜상 | d(억) | d(%%)" % "종목")
print("-"*72)
for name,(v,jj) in cases.items():
    ex=[x for x in v if x!=jj]
    a0,a1=q40(v),q40(ex)
    d=a1-a0; pct=100*d/a0
    print("%-18s | %2d | %5d  |  %5d    | %+5d | %+5.1f%%" % (name,len(v),a0,a1,d,pct))
