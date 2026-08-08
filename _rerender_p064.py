# -*- coding: utf-8 -*-
# STEP 4.7 — p.64 제목 수익률 + 삼성제약 최고 라벨 + 대유플러스 차트 헤더(축과 불일치 의심)
import fitz, os

SRC = r'D:\StockAnalyst\금융공자_가이드북\단타매매\단타 매매 가이드북 4권\4-1권\단타 매매 가이드북 4-1권.pdf'
OUT = r'D:\StockAnalyst\book_extracts\_append_log\_rerender'
os.makedirs(OUT, exist_ok=True)

doc = fitz.open(SRC)
pg = doc[63]                      # page_064.jpg
W, H = pg.rect.width, pg.rect.height

crops = {
    'title1': (0.02, 0.077, 0.98, 0.112),   # 삼성제약 제목
    'title2': (0.02, 0.452, 0.98, 0.487),   # 대유플러스 제목
    'hdr1':   (0.02, 0.122, 0.45, 0.165),   # 삼성제약 헤더 + 최고 라벨
    'hdr2':   (0.02, 0.497, 0.45, 0.540),   # 대유플러스 헤더 + 최고 라벨
    'axis2':  (0.88, 0.497, 0.99, 0.800),   # 대유플러스 우측 가격축
}
for name, (x0, y0, x1, y1) in crops.items():
    clip = fitz.Rect(x0 * W, y0 * H, x1 * W, y1 * H)
    pix = pg.get_pixmap(matrix=fitz.Matrix(14, 14), clip=clip)
    p = os.path.join(OUT, 'p064_%s.png' % name)
    pix.save(p)
    print('%-7s -> %s (%d x %d)' % (name, p, pix.width, pix.height))
doc.close()
