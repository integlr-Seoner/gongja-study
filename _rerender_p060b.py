# -*- coding: utf-8 -*-
# p.60 툴팁 '거래량' 줄만 초고배율 (적색 박스 겹침 구간 확인용)
import fitz, os

SRC = r'D:\StockAnalyst\금융공자_가이드북\단타매매\단타 매매 가이드북 4권\4-1권\단타 매매 가이드북 4-1권.pdf'
OUT = r'D:\StockAnalyst\book_extracts\_append_log\_rerender'
os.makedirs(OUT, exist_ok=True)

doc = fitz.open(SRC)
pg = doc[59]
W, H = pg.rect.width, pg.rect.height

# 툴팁 crop(0.36H~0.60H) 안에서 거래량 줄은 y≈820/1685 → 절대 y ≈ 0.36H + 0.487*0.24H
for tag, y0f, y1f in (('vol', 0.4520, 0.4700), ('vol_wide', 0.4400, 0.4850)):
    clip = fitz.Rect(0.05 * W, y0f * H, 0.36 * W, y1f * H)
    pix = pg.get_pixmap(matrix=fitz.Matrix(22, 22), clip=clip)
    p = os.path.join(OUT, 'p060_%s.png' % tag)
    pix.save(p)
    print('%-9s -> %s (%d x %d)' % (tag, p, pix.width, pix.height))
doc.close()
