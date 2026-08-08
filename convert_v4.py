import fitz
import os

pdf_path = r'D:\StockAnalyst\금융공자_가이드북\재료매매\재료 분석 가이드북 (4권).pdf'
out_dir = r'D:\StockAnalyst\book_extracts\gongja_vision\v4_pages'

os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
total = len(doc)
print(f'변환 시작: {total} 페이지')

mat = fitz.Matrix(2.0, 2.0)  # 2배 해상도 (v3와 동일)

for i in range(total):
    page = doc[i]
    pix = page.get_pixmap(matrix=mat)
    out_path = os.path.join(out_dir, f'page_{i+1:03d}.jpg')
    pix.save(out_path)
    if (i+1) % 50 == 0:
        print(f'  {i+1}/{total} 완료')

doc.close()
print(f'변환 완료: {total} 페이지')

files = [f for f in os.listdir(out_dir) if f.endswith('.jpg')]
print(f'파일 개수: {len(files)}')
