# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = r"D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md"
print("EXISTS:", os.path.exists(p))
if os.path.exists(p):
    print("SIZE:", os.path.getsize(p))
    with open(p, encoding='utf-8') as f:
        print(f.read())
