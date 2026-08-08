"""검증 사전조사: ohlcv_long.db의 종목 코드 구성
- 코드 끝자리 분포 (우선주 분류 가능성)
- 코드 첫자리 분포 (시장 구분: 0/3=KOSPI, 1/2/7/8/9=KOSDAQ 등)
"""
import sqlite3
from collections import Counter

DB = r'D:\StockAnalyst\ohlcv_long.db'
conn = sqlite3.connect(DB, timeout=30)

rows = conn.execute("SELECT DISTINCT code FROM daily_ohlcv_long").fetchall()
codes = [r[0] for r in rows]

print(f'고유 종목 수: {len(codes):,}')
print()

# 끝자리 분포
last_digits = Counter(c[-1] for c in codes)
print('코드 끝자리 분포 (마지막 1자리):')
for d in sorted(last_digits.keys()):
    cnt = last_digits[d]
    pct = cnt / len(codes) * 100
    marker = ' ← 보통주(끝0)' if d == '0' else ' ← 우선주/기타'
    print(f'  {d}: {cnt:>5,}개 ({pct:>5.2f}%){marker}')

# 우선주(끝 != 0) 샘플 10개
print('\n끝자리 0 아닌 종목 샘플 10개 (우선주 추정):')
non_ord = [c for c in codes if c[-1] != '0']
for c in non_ord[:10]:
    print(f'  {c}')

# 6자리가 아닌 코드가 있는지 (ETN은 6자리 아닐 수도)
non6 = [c for c in codes if len(c) != 6]
print(f'\n6자리 아닌 코드: {len(non6)}개')
for c in non6[:10]:
    print(f'  {c} (길이 {len(c)})')

# 숫자가 아닌 코드
non_digit = [c for c in codes if not c.isdigit()]
print(f'\n숫자 아닌 문자 포함된 코드: {len(non_digit)}개')
for c in non_digit[:10]:
    print(f'  {c}')

conn.close()
