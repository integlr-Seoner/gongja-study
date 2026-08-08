# -*- coding: utf-8 -*-
# 스윙매매 가이드북 PDF → JPG 변환기 (_conv_susik.py 동일 패턴)
# 원본 PDF는 사실상 전량 이미지(텍스트 레이어 없음) → 정본 판단 기준 = PDF 페이지 이미지.
import fitz, os

BASE = r'D:\StockAnalyst\금융공자_가이드북\스윙매매'
OUT  = r'D:\StockAnalyst\book_extracts\gongja_vision\chart_pages\13_스윙매매'
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
    G = r'스윙 매매 가이드북 1 ~ 6권'
    B = r'기준봉 캔들 패턴 추적 자료집'
    convert(os.path.join(G, r'스윙 매매 가이드북 1권.pdf'), '01_1권')                    # 126p
    convert(os.path.join(G, r'스윙 매매 가이드북 2권.pdf'), '02_2권')                    # 207p
    convert(os.path.join(G, r'스윙 매매 가이드북 3권.pdf'), '03_3권')                    # 336p
    convert(os.path.join(G, r'스윙 매매 가이드북 4권.pdf'), '04_4권')                    # 214p
    convert(os.path.join(G, r'스윙 매매 가이드북 5권.pdf'), '05_5권')                    # 281p
    convert(os.path.join(G, r'스윙 매매 가이드북 6권.pdf'), '06_6권')                    # 148p
    convert(os.path.join(G, r'거래대금의 디테일한 분석 관점 자료집.pdf'), '07_거래대금디테일')  # 218p ★단타 S11 중복 의심
    convert(os.path.join(G, r'종목의 특징과 성격 이론 보충 자료.pdf'), '08_종목특징성격')      # 83p
    convert(os.path.join(G, r'주가와 재료의 관계 PDF.pdf'), '09_주가재료관계')              # 93p
    convert(os.path.join(B, r'기준봉 캔들 패턴 추적 Part. 01.pdf'), '10_기준봉Part01')      # 204p
    convert(os.path.join(B, r'기준봉 캔들 패턴 추적 Part. 02.pdf'), '11_기준봉Part02')      # 177p
    convert(os.path.join(B, r'기준봉 캔들 패턴 추적 Part. 03.pdf'), '12_기준봉Part03')      # 184p
    convert(r'스윙 매매 Q & A.pdf', '13_스윙QA')                                        # 136p
    # 설문 PDF.pdf(1p) = 변환 제외
