# -*- coding: utf-8 -*-
import fitz, os

BASE = r'D:\StockAnalyst\금융공자_가이드북\차트매매\일봉 차트 수급 추적 자료집'
OUT  = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages'
SCALE, Q = 1.7, 72

def info():
    for p in ['1부', '2부', '3부']:
        src = os.path.join(BASE, f'일봉 차트 수급 추적 자료집 - {p}.pdf')
        d = fitz.open(src)
        txt = sum(len(d[i].get_text()) for i in range(len(d)))
        print(f'{p}: {len(d)}p | text_layer={txt}chars')
        d.close()

def convert(part, sub):
    src = os.path.join(BASE, f'일봉 차트 수급 추적 자료집 - {part}.pdf')
    dst = os.path.join(OUT, sub)
    os.makedirs(dst, exist_ok=True)
    doc = fitz.open(src); n = len(doc); mx = 0
    for i in range(n):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
        b = pix.tobytes('jpeg', jpg_quality=Q)
        with open(os.path.join(dst, f'page_{i+1:03d}.jpg'), 'wb') as f:
            f.write(b)
        mx = max(mx, len(b))
    doc.close()
    print(f'DONE {sub}: {n}p, max={mx/1024:.0f}KB')

if __name__ == '__main__':
    info()
    convert('1부', '07_일봉수급추적_1')
