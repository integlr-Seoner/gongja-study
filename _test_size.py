# -*- coding: utf-8 -*-
import fitz, os
BASE = r'D:\StockAnalyst\금융공자_가이드북\차트매매'
doc = fitz.open(os.path.join(BASE, '차트 매매 기본서 - 상 (1권).pdf'))
pg = doc[10]
for scale in (2.0, 1.5, 1.3, 1.1):
    for q in (75, 60):
        pix = pg.get_pixmap(matrix=fitz.Matrix(scale, scale))
        b = pix.tobytes('jpeg', jpg_quality=q)
        print(f'scale={scale} q={q} -> {len(b)/1024:.0f} KB  ({pix.width}x{pix.height})')
doc.close()
