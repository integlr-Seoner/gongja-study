# -*- coding: utf-8 -*-
# STEP 4.7 — p.60 EDGC 1분봉 툴팁 고배율 재렌더링 (수치 = 판정 근거)
import fitz, os

SRC = r'D:\StockAnalyst\금융공자_가이드북\단타매매\단타 매매 가이드북 4권\4-1권\단타 매매 가이드북 4-1권.pdf'
OUT = r'D:\StockAnalyst\book_extracts\_append_log\_rerender'
os.makedirs(OUT, exist_ok=True)

doc = fitz.open(SRC)
pg = doc[59]                      # page_060.jpg = 0-index 59
W, H = pg.rect.width, pg.rect.height
print('page rect: %.1f x %.1f' % (W, H))

# 툴팁 박스 = 페이지 좌측 상단~중단. 여유 있게 잡는다.
crops = {
    'tooltip': fitz.Rect(0.03 * W, 0.36 * H, 0.38 * W, 0.60 * H),
    'infobar': fitz.Rect(0.03 * W, 0.33 * H, 0.97 * W, 0.40 * H),
}
for name, clip in crops.items():
    pix = pg.get_pixmap(matrix=fitz.Matrix(9, 9), clip=clip)
    path = os.path.join(OUT, 'p060_%s.png' % name)
    pix.save(path)
    print('%-8s -> %s  (%d x %d)' % (name, path, pix.width, pix.height))
doc.close()
