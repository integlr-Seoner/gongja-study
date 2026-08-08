# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')

folder = r'D:\StockAnalyst\금융공자_가이드북\재료매매'
files = sorted(os.listdir(folder))
print(f'== 재료매매 폴더 전체 PDF ==')
for f in files:
    full = os.path.join(folder, f)
    if os.path.isfile(full) and f.lower().endswith('.pdf'):
        size = os.path.getsize(full) / (1024*1024)
        print(f'  {f} | {size:.1f} MB')
    elif os.path.isdir(full):
        print(f'  [DIR] {f}')
