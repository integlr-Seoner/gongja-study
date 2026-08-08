# -*- coding: utf-8 -*-
# 수식관리자 가이드북 PDF → JPG 변환기 (_conv_danta.py 동일 패턴)
# 원본 PDF는 사실상 전량 이미지(텍스트 레이어 없음) → 정본 판단 기준 = PDF 페이지 이미지.
import fitz, os

BASE = r'D:\StockAnalyst\금융공자_가이드북\수식관리자'
OUT  = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages\12_수식관리자'
SCALE, Q = 1.7, 72   # 기존과 동일

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
    convert(r'01. 수식관리자 기본편.pdf', '01_기본편')                              # 221p
    convert(r'02. 수식관리자 심화편.pdf', '02_심화편')                              # 210p
    convert(r'03. 수식관리자 부록편.pdf', '03_부록편')                              # 89p
    convert(r'04. 수식관리자 메모장.pdf', '04_메모장')                              # 12p
    convert(r'05. 수식관리자 함수 레시피 자료집\수식관리자 함수 레시피 1권.pdf', '05_레시피1권')  # 163p
    convert(r'05. 수식관리자 함수 레시피 자료집\수식관리자 함수 레시피 2권.pdf', '06_레시피2권')  # 298p
    convert(r'06. 수식관리자 Q & A 자료집\수식관리자 Q & A 자료집.pdf', '07_QA자료집')          # 180p
