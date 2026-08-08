# -*- coding: utf-8 -*-
# 단타매매 4권 부속 자료집 → 페이지 이미지 변환
# 폴더 관례: 권은 순번(01_1권 ~ 05_4-1권, 다음 4-2권은 06_), 자료집은 'S' 접두어로 구분
import fitz, os

BASE = r'D:\StockAnalyst\금융공자_가이드북\단타매매\단타 매매 가이드북 4권\4-1권'
OUT = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages\11_단타매매'
SCALE, Q = 1.7, 72   # _conv_danta.py 와 동일 설정

JOBS = [
    ('갭하락 단타 매매 요약집 (4-1권 요약).pdf', 'S01_갭하락_요약집'),
    ('갭하락 단타 매매 흐름 예시.pdf',            'S02_갭하락_흐름예시'),
]


def convert(rel, sub):
    src = os.path.join(BASE, rel)
    dst = os.path.join(OUT, sub)
    if not os.path.exists(src):
        print('!! 원본 없음:', src)
        return
    os.makedirs(dst, exist_ok=True)
    doc = fitz.open(src)
    n = len(doc)
    mx = 0
    for i in range(n):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
        b = pix.tobytes('jpeg', jpg_quality=Q)
        with open(os.path.join(dst, 'page_%03d.jpg' % (i + 1)), 'wb') as f:
            f.write(b)
        mx = max(mx, len(b))
    doc.close()
    print('DONE %-22s : %3dp, max=%dKB' % (sub, n, mx / 1024))


if __name__ == '__main__':
    for rel, sub in JOBS:
        convert(rel, sub)
