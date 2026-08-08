# -*- coding: utf-8 -*-
# STEP 4.7 — p.63 사례 제목의 수익률 수치 + 차트 헤더/라벨 확인
import fitz, os

SRC = r'D:\StockAnalyst\금융공자_가이드북\단타매매\단타 매매 가이드북 4권\4-1권\단타 매매 가이드북 4-1권.pdf'
OUT = r'D:\StockAnalyst\book_extracts\_append_log\_rerender'
os.makedirs(OUT, exist_ok=True)

doc = fitz.open(SRC)
pg = doc[62]                      # page_063.jpg
W, H = pg.rect.width, pg.rect.height
print('page rect: %.1f x %.1f' % (W, H))

crops = {
    'title1': (0.02, 0.230, 0.98, 0.270),   # 이오플로우 제목
    'title2': (0.02, 0.615, 0.98, 0.655),   # EDGC 제목
    'hdr1':   (0.02, 0.278, 0.55, 0.302),   # 차트1 헤더(시고저종)
    'lbl1':   (0.02, 0.285, 0.35, 0.320),   # 차트1 최고 라벨
    'hdr2':   (0.02, 0.660, 0.55, 0.685),   # 차트2 헤더
}
for name, (x0, y0, x1, y1) in crops.items():
    clip = fitz.Rect(x0 * W, y0 * H, x1 * W, y1 * H)
    pix = pg.get_pixmap(matrix=fitz.Matrix(14, 14), clip=clip)
    p = os.path.join(OUT, 'p063_%s.png' % name)
    pix.save(p)
    print('%-7s -> %s (%d x %d)' % (name, p, pix.width, pix.height))
doc.close()
