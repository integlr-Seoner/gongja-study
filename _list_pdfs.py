# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
folder = r'D:\StockAnalyst\금융공자_가이드북'
files = sorted(os.listdir(folder))
pdfs = [f for f in files if f.lower().endswith('.pdf')]
print(f'Total PDFs: {len(pdfs)}')
print('=' * 80)
for i, f in enumerate(pdfs, 1):
    full = os.path.join(folder, f)
    size = os.path.getsize(full) / (1024*1024)
    print(f'{i:3d}. {f}')
    print(f'     Size: {size:.2f} MB')
