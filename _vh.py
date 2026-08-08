# -*- coding: utf-8 -*-
import io, os
h = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'
t = io.open(h, encoding='utf-8').read()
print('bytes: %d / chars: %d / lines: %d' % (os.path.getsize(h), len(t), t.count('\n') + 1))
print()
NEW = ['headers 1853', 'last G 1980', 'page_021', 'G1981',
       'S01 20/26p', '재료 소멸 AND NOT', '1등주', 'p.1~20 완료']
OLD = ['headers 1843', 'page_011', 'S01 10/26p', 'G1971부터']
print('=== 신규값 (적용 후 있어야 함) ===')
for k in NEW:
    print('  %-22s %s' % (k, 'OK' if k in t else '없음'))
print('=== 낡은값 (적용 후 없어야 함) ===')
for k in OLD:
    print('  %-22s %s' % (k, '남음' if k in t else '제거'))
print()
print('=== 판정 ===')
applied = all(k in t for k in NEW) and not any(k in t for k in OLD)
print('적용 완료' if applied else '아직 미적용 (또는 부분 적용)')
