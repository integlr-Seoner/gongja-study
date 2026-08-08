import os

notes_dir = r'D:\StockAnalyst\book_extracts\학습노트'

# 핸드오버 파일
handover = os.path.join(notes_dir, 'HANDOVER_3권_정독.md')
print('=== 핸드오버 파일 ===')
print('경로:', handover)
print('존재:', os.path.exists(handover))
print('크기:', f'{os.path.getsize(handover)/1024:.1f} KB')
with open(handover, 'r', encoding='utf-8') as f:
    lines = sum(1 for _ in f)
print('줄수:', lines)

# 02d 노트
print()
print('=== 02d 노트 ===')
note = os.path.join(notes_dir, '02d_금융공자_3권보강.md')
print('경로:', note)
print('존재:', os.path.exists(note))
print('크기:', f'{os.path.getsize(note)/1024:.1f} KB')
with open(note, 'r', encoding='utf-8') as f:
    lines = sum(1 for _ in f)
print('줄수:', lines)

# JPEG 폴더
print()
print('=== JPEG 폴더 ===')
jpeg_dir = r'D:\StockAnalyst\book_extracts\gongja_vision\v3_pages'
files = sorted([f for f in os.listdir(jpeg_dir) if f.endswith('.jpg')])
print('경로:', jpeg_dir)
print('파일 개수:', len(files))
print('첫 파일:', files[0])
print('마지막 파일:', files[-1])
next_page = os.path.join(jpeg_dir, 'page_011.jpg')
print('다음 정독 page_011.jpg 존재:', os.path.exists(next_page))
