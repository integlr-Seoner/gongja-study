# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
t = open(r'D:\StockAnalyst\krx_api.py', encoding='utf-8').read()
print('파일 크기: %d자 / %d줄' % (len(t), len(t.splitlines())))
print()
print('--- def / class ---')
for m in re.finditer(r'^(?:class|def)\s+(\w+)\s*\(([^)]*)\)', t, re.M):
    print('  %-34s (%s)' % (m.group(1), m.group(2)[:66]))
print()
print('--- URL / endpoint ---')
for u in sorted(set(re.findall(r'https?://[^\s\'\"]+', t))):
    print('  ' + u)
print()
print('--- 상수 ---')
for m in re.finditer(r'^([A-Z][A-Z_0-9]{2,})\s*=\s*(.{0,58})', t, re.M):
    print('  %-26s %s' % (m.group(1), m.group(2)))
print()
print('--- docstring 첫 20줄 ---')
print('\n'.join(t.splitlines()[:20]))
