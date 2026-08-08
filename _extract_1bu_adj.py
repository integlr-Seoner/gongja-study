# -*- coding: utf-8 -*-
"""파일10(일봉수급추적 1부)에서 사례별 종목명 + 저자 적정거래대금 추출"""
import io, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
fp = r"D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md"
lines = io.open(fp, encoding="utf-8").readlines()

hdr = re.compile(r'^## G(\d+)\.\s*\[사례(\d+)\s+([^\]\s]+)')
# 사례별 라인 그룹핑
cases = {}   # num -> {'name':.., 'g':.., 'lines':[..]}
cur = None
for l in lines:
    m = hdr.match(l)
    if m:
        num = int(m.group(2)); name = m.group(3)
        if num not in cases:
            cases[num] = {'name': name, 'g': int(m.group(1)), 'lines': []}
        cur = num
    if cur is not None:
        cases[cur]['lines'].append(l)

# 각 사례의 첫 '적정거래대금 ... 숫자' 추출
adjpat = re.compile(r'적정거래대금\s*[:\-]?\s*(?:약\s*)?([\d,]+)\s*(?:~\s*([\d,]+))?\s*억')
def num(s): return int(s.replace(',', ''))
print("사례 | 종목명 | 적정거래대금(원문) | 대표값")
for n in sorted(cases):
    c = cases[n]; found = None
    for l in c['lines']:
        m = adjpat.search(l)
        if m:
            lo = num(m.group(1)); hi = num(m.group(2)) if m.group(2) else None
            rep = (lo+hi)//2 if hi else lo
            found = (('%d~%d' % (lo,hi)) if hi else str(lo), rep)
            break
    print("#%02d | %-14s | %s | %s" % (n, c['name'], found[0] if found else '(없음)', found[1] if found else '-'))
