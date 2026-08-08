"""koa_devguide.xml의 NXT 핵심 섹션 전체 블록 추출"""
import re

with open(r'D:\StockAnalyst\_v_15_koa_devguide_snapshot.xml', 'rb') as f:
    text = f.read().decode('euc-kr', errors='replace')

lines = text.split('\n')

# 주요 블록 범위
blocks = [
    (25, 50, '대체거래소 지원 - FID 215'),
    (270, 370, '대체거래소 - 조회·실시간 시세'),
    (775, 800, '대체거래소 주문 유형'),
    (1470, 1490, 'NXT 종목 구분'),
    (1830, 1900, '스톱지정가 주문 예시'),
]

for start, end, label in blocks:
    print('=' * 80)
    print(f'블록: {label} (라인 {start}~{end})')
    print('=' * 80)
    for i in range(start-1, min(end, len(lines))):
        ln = lines[i].rstrip()
        if ln.strip():
            print(f'{i+1:5}: {ln}')
    print()
