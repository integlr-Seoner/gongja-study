"""koa_devguide.xml NXT 관련 섹션 추출 (EUC-KR 인코딩)
목적: 키움 OpenAPI+ 의 NXT TR/FID/시세 스펙 실측
"""
import re

SRC = r'D:\StockAnalyst\_v_15_koa_devguide_snapshot.xml'

with open(SRC, 'rb') as f:
    raw = f.read()

text = raw.decode('euc-kr', errors='replace')

print('=' * 80)
print('koa_devguide.xml NXT 관련 전수 추출')
print(f'총 길이: {len(text):,} 문자')
print('=' * 80)

# NXT, _NX, _AL 등장 라인 전수
lines = text.split('\n')
print(f'총 {len(lines)} 라인\n')

nxt_lines = []
for i, ln in enumerate(lines, 1):
    if re.search(r'NXT|_NX|_AL|넥스트|SOR|대체거래', ln):
        nxt_lines.append((i, ln.rstrip()))

print(f'NXT 관련 라인 수: {len(nxt_lines)}')
print('-' * 80)
for ln_no, ln in nxt_lines[:150]:
    print(f'{ln_no:5}: {ln}')
