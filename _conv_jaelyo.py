# -*- coding: utf-8 -*-
# 재료매매 트랙 잔여분(5·6권 + 상한가 데이터 3 + Q&A) PDF → JPG (_conv_swing.py 동일 패턴)
import fitz, os, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'D:\StockAnalyst\금융공자_가이드북\재료매매'
OUT  = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages\14_재료매매'
SCALE, Q = 1.7, 72

def convert(rel, sub):
    src = os.path.join(BASE, rel); dst = os.path.join(OUT, sub)
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
    convert(r'재료 분석 가이드북 (5권).pdf', '05_5권')                          # 219p
    convert(r'재료 분석 가이드북 (6권).pdf', '06_6권')                          # 264p
    convert(os.path.join('상한가 데이터 자료집', '상한가 추적 - 2022년 1월.pdf'), '07_상한가2201')  # 197p
    convert(os.path.join('상한가 데이터 자료집', '상한가 추적 - 2022년 2월.pdf'), '08_상한가2202')  # 169p
    convert(os.path.join('상한가 데이터 자료집', '상한가 추적 - 2022년 3월.pdf'), '09_상한가2203')  # 206p
    convert(os.path.join('재료 매매 Q & A', '재료 매매 Q & A Ver. 01.pdf'), '10_QA')            # 201p
    print('ALL DONE')
