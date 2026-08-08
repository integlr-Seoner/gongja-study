# -*- coding: utf-8 -*-
import fitz, os

BASE = r'D:\StockAnalyst\금융공자_가이드북\차트매매'
OUT  = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages'
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
    # convert('차트 매매 기본서 - 상 (1권).pdf', '01_기본서상')  # 완료
    # convert('차트 매매 기본서 - 중 (2권).pdf', '02_기본서중')  # 완료
    # convert('차트 매매 기본서 - 하 (3권).pdf', '03_기본서하')  # 완료
    # convert('차트 매매 기본서 - 부록.pdf', '04_부록')  # 완료
    # convert('적정 거래대금 이론 보충 자료.pdf', '05_적정거래대금')  # 완료
    # convert(r'일봉 차트 수급 추적 자료집\일봉 차트 수급 추적 자료집 - 1부.pdf', '07_일봉수급추적_1')  # 완료(217p)
    # convert(r'일봉 차트 수급 추적 자료집\일봉 차트 수급 추적 자료집 - 2부.pdf', '07_일봉수급추적_2')  # 완료(198p)
    # convert(r'일봉 차트 수급 추적 자료집\일봉 차트 수급 추적 자료집 - 3부.pdf', '07_일봉수급추적_3')  # 완료(199p)
    convert('차트 매매 가이드북 - Q & A 자료집.pdf', '06_QA자료집')
