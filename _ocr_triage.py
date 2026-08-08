# -*- coding: utf-8 -*-
"""3-2권 OCR 페이지별 텍스트량 측정 → 업로드 필요 페이지 선별용(읽기 전용)"""
import re

SRC = r'D:\StockAnalyst\book_extracts\금융공자_OCR\단타매매\단타 매매 가이드북 3권\단타 매매 가이드북 3-2권_clean.txt'

txt = open(SRC, encoding='utf-8', errors='replace').read()
parts = re.split(r'\[ p\.(\d+) \| ocr \]', txt)

pages = []
for i in range(1, len(parts), 2):
    no = int(parts[i])
    body = parts[i+1].replace('=', '').strip()
    han = len(re.findall(r'[가-힣]', body))
    pages.append((no, han))

lo  = [p for p, h in pages if h < 100]
mid = [p for p, h in pages if 100 <= h < 300]
hi  = [p for p, h in pages if h >= 300]

print(f'총 페이지: {len(pages)}')
print(f'  한글 300자+ (산문 위주, OCR로 충분 가능성) : {len(hi)}p')
print(f'  한글 100~299자 (혼합)                      : {len(mid)}p')
print(f'  한글 100자 미만 (이미지/목차 위주, 업로드 필수): {len(lo)}p')
print()
print('■ 100자 미만 페이지 =', lo)
print()
print('■ 100~299자 페이지 =', mid)
