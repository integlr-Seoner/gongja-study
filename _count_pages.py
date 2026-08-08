# -*- coding: utf-8 -*-
"""금융공자_가이드북 전체 PDF 페이지 수 실측(읽기 전용)"""
import fitz, os

ROOT = r'D:\StockAnalyst\금융공자_가이드북'
CATS = ['재료매매', '차트매매', '스윙매매', '단타매매', '수식관리자', '조건검색기']

OUTF = open(r'D:\StockAnalyst\book_extracts\_pages_out.txt', 'w', encoding='utf-8')
def print(*a, **k):
    OUTF.write(' '.join(str(x) for x in a) + '\n')

total = 0
for c in CATS:
    base = os.path.join(ROOT, c)
    if not os.path.isdir(base):
        print(f'[{c}] 폴더 없음'); continue
    sub = 0; rows = []
    for dp, _, fns in os.walk(base):
        for fn in fns:
            if not fn.lower().endswith('.pdf'):
                continue
            p = os.path.join(dp, fn)
            try:
                d = fitz.open(p); n = len(d); d.close()
            except Exception as e:
                rows.append((fn, f'ERR {e}')); continue
            rows.append((fn, n)); sub += n
    print(f'===== {c} : {sub}p ({len(rows)}개 PDF) =====')
    for fn, n in sorted(rows, key=lambda x: str(x[1]), reverse=True):
        print(f'   {n:>5} | {fn}')
    total += sub
    print()
print(f'@@@ 전체 PDF 합계 = {total}p')
