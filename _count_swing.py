# -*- coding: utf-8 -*-
import fitz, os
BASE = r'D:\StockAnalyst\금융공자_가이드북\스윙매매'
rels = []
for root, _, files in os.walk(BASE):
    for fn in sorted(files):
        if fn.lower().endswith('.pdf'):
            rels.append(os.path.relpath(os.path.join(root, fn), BASE))
rels.sort()
total = 0
for rel in rels:
    doc = fitz.open(os.path.join(BASE, rel)); n = len(doc); doc.close()
    total += n
    print(f'{n:4d}p  {rel}')
print(f'---- total {total}p across {len(rels)} files')
