# -*- coding: utf-8 -*-
# 재료매매 트랙 잔여분 PDF 인벤토리(페이지 수 포함)
import fitz, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = r'D:\StockAnalyst\금융공자_가이드북\재료매매'
total = 0
for root, dirs, files in os.walk(BASE):
    dirs.sort()
    pdfs = sorted([f for f in files if f.lower().endswith('.pdf')])
    if not pdfs:
        continue
    rel = os.path.relpath(root, BASE)
    print(f'[{rel}]')
    for f in pdfs:
        try:
            d = fitz.open(os.path.join(root, f)); n = len(d); d.close()
        except Exception as e:
            n = f'ERR({e})'
        print(f'   {f}  = {n}p')
        if isinstance(n, int):
            total += n
print(f'TOTAL PDF pages = {total}')
