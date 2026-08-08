import io
PATH = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'
OUT = r'D:\StockAnalyst\book_extracts\_nextstart.txt'
txt = io.open(PATH, encoding='utf-8-sig').read()
key = 'page_025.jpg'
i = txt.find(key)
# back up to the start of the "★★★5-1권+..." marker sentence
start = txt.rfind('★★★5-1권+', 0, i)
seg = txt[start:i+360]
io.open(OUT, 'w', encoding='utf-8').write(seg)
print('LEN', len(seg), 'COUNT_marker', txt.count(key))
