# -*- coding: utf-8 -*-
"""90종 → 종목코드 확정 (현재명 + 前명 정확일치)"""
import io, sys, json, re
sys.path.insert(0, r'D:\StockAnalyst')
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from krx_api import get_krx_api

api = get_krx_api()
# 최근일 + 과거일 2개로 이름 사전 구축(개명 대응)
NAME2CODE = {}
for d in [None, '20210324', '20201123', '20211202', '20220certain'][:4]:
    for r in api.get_stock_price_by_date(d):
        NAME2CODE.setdefault(r['name'].strip(), r['code'])

targets = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, _ in stocks:
        cur = name.split('(')[0].strip()
        m = re.search(r'前\s*([^)]+)\)', name)
        old = m.group(1).strip() if m else None
        targets.append((part, name, cur, old))

out, miss = {}, []
for part, name, cur, old in targets:
    code = NAME2CODE.get(cur) or (NAME2CODE.get(old) if old else None)
    if code:
        out[name] = {'code': code, 'cur': cur, 'old': old}
    else:
        miss.append((part, name, cur, old))

print('해결 %d / 90종' % len(out))
print('★개명 종목(前명으로 해결):')
for k, v in out.items():
    if v['old'] and NAME2CODE.get(v['cur']) is None:
        print('   %-28s → %s (前 %s)' % (k, v['code'], v['old']))
print('★미해결 %d종:' % len(miss))
for p, n, c, o in miss:
    print('   [%s] %s | cur=%r old=%r' % (p, n, c, o))
json.dump(out, open(r'D:\StockAnalyst\book_extracts\_code_map.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
