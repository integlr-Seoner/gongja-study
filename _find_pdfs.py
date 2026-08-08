# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding='utf-8')

# 검색 후보 폴더들
base = r'D:\StockAnalyst'
print(f'== Listing {base} ==')
for f in sorted(os.listdir(base)):
    full = os.path.join(base, f)
    if os.path.isdir(full):
        print(f'[DIR ] {f}')
    else:
        size = os.path.getsize(full) / (1024*1024)
        if f.lower().endswith('.pdf'):
            print(f'[PDF ] {f} | {size:.1f} MB')
        elif size > 1:
            print(f'[FILE] {f} | {size:.1f} MB')

# 가능한 가이드북 폴더 후보 검색
print('\n== Searching for 금융공자/guide folders ==')
for root, dirs, files in os.walk(base):
    if '금융공자' in root or '가이드' in root or 'gongja' in root.lower() or 'guide' in root.lower():
        if 'venv' in root or 'node_modules' in root or '.git' in root:
            continue
        rel = os.path.relpath(root, base)
        pdfs = [f for f in files if f.lower().endswith('.pdf')]
        if pdfs:
            print(f'\n  [{rel}] - {len(pdfs)} PDFs')
            for p in sorted(pdfs)[:5]:
                size = os.path.getsize(os.path.join(root, p)) / (1024*1024)
                print(f'    - {p} ({size:.1f} MB)')
            if len(pdfs) > 5:
                print(f'    ... and {len(pdfs)-5} more')
