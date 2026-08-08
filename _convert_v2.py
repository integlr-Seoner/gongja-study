# -*- coding: utf-8 -*-
"""금융공자 재료 분석 가이드북 (2권) PDF → JPEG 변환 (1권과 동일 방식)"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')

src = r'D:\StockAnalyst\금융공자_가이드북\재료매매\재료 분석 가이드북 (2권).pdf'
dst_dir = r'D:\StockAnalyst\book_extracts\gongja_vision\v2_pages'
os.makedirs(dst_dir, exist_ok=True)

print(f'Source: {src}')
print(f'Source exists: {os.path.exists(src)}')
print(f'Source size: {os.path.getsize(src) / (1024*1024):.1f} MB')
print(f'Destination: {dst_dir}')

# PyMuPDF로 변환
import fitz  # PyMuPDF

doc = fitz.open(src)
total = doc.page_count
print(f'\nTotal pages: {total}')
print(f'DPI: 100 (1권과 동일)')
print('=' * 60)

# 100 DPI = zoom 100/72 ≈ 1.389
zoom = 100 / 72
mat = fitz.Matrix(zoom, zoom)

for i, page in enumerate(doc, 1):
    pix = page.get_pixmap(matrix=mat)
    out_path = os.path.join(dst_dir, f'page_{i:03d}.jpg')
    pix.save(out_path)
    if i % 20 == 0 or i == total:
        print(f'  Saved {i}/{total}')

doc.close()
print(f'\n✅ Conversion complete: {total} pages → {dst_dir}')
