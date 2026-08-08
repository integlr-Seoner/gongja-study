# -*- coding: utf-8 -*-
"""3-2권 p.11~30 OCR 본문 추출 + 이미지 필요 페이지 선별(읽기 전용)"""
import re

SRC = r'D:\StockAnalyst\book_extracts\금융공자_OCR\단타매매\단타 매매 가이드북 3권\단타 매매 가이드북 3-2권_clean.txt'
OUT = r'D:\StockAnalyst\book_extracts\_ocr_p11_30.txt'

txt = open(SRC, encoding='utf-8', errors='replace').read()
parts = re.split(r'\[ p\.(\d+) \| ocr \]', txt)

pages = {}
for i in range(1, len(parts), 2):
    pages[int(parts[i])] = parts[i+1].replace('=', '').strip()

with open(OUT, 'w', encoding='utf-8') as f:
    for n in range(11, 31):
        b = pages.get(n, '')
        han = len(re.findall(r'[가-힣]', b))
        f.write(f'\n########## p.{n}  (한글 {han}자) ##########\n{b}\n')
print('done')
