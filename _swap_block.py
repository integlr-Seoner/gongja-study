# -*- coding: utf-8 -*-
# 핸드오버 「⚡ 새 창 즉시 시작」 블록 교체 (L3~L209만, L210 이후 보존)
# 경계를 실측 검증한 뒤에만 쓴다. --apply 없이 실행하면 미리보기만 한다.
import io, sys

P = r'D:\StockAnalyst\book_extracts\학습노트\HANDOVER_가이드북_트랙정독.md'
NEW = r'D:\StockAnalyst\book_extracts\_new_block.md'
START, END = 3, 209           # 1-indexed, 양끝 포함
GUARD_START = '> ## ⚡ 새 창 즉시 시작 (2026-07-24'
GUARD_END = '> ### ▶ 인수 대상 지식 상태'

old = io.open(P, encoding='utf-8').read().split('\n')
new = io.open(NEW, encoding='utf-8').read().rstrip('\n').split('\n')

# --- 경계 검증 ---
ok = True
if not old[START - 1].startswith(GUARD_START):
    print('!! L%d 가 07-24 블록 헤더가 아님: %r' % (START, old[START - 1][:60])); ok = False
if not old[END].startswith(GUARD_END):
    print('!! L%d(교체 직후)가 「인수 대상 지식 상태」가 아님: %r' % (END + 1, old[END][:60])); ok = False
cnt = sum(1 for l in old if l.startswith('> ## ⚡ 새 창 즉시 시작'))
if cnt != 1:
    print('!! 「즉시 시작」 헤더가 %d개 (1개여야 함)' % cnt); ok = False
if not ok:
    print('\n경계 검증 실패 — 쓰지 않고 중단'); sys.exit(1)

print('경계 검증 OK')
print('  교체 대상 : L%d ~ L%d (%d줄)' % (START, END, END - START + 1))
print('  신규 블록 : %d줄' % len(new))
print('  보존 시작 : L%d = %s' % (END + 1, old[END][:50]))
print('  총 줄수   : %d -> %d' % (len(old), len(old) - (END - START + 1) + len(new)))

if '--apply' not in sys.argv:
    print('\n[미리보기] --apply 를 붙이면 실제로 씁니다.')
    sys.exit(0)

out = old[:START - 1] + new + old[END:]
io.open(P, 'w', encoding='utf-8', newline='').write('\n'.join(out))
print('\n교체 완료: %d줄' % len(out))
