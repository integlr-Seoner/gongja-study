import io, sys, os
p = r'D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md'
lines = open(p, encoding='utf-8').readlines()
print('BEFORE total lines:', len(lines))
idx = None
for i, l in enumerate(lines):
    if l.startswith('## G868.'):
        idx = i
        break
if idx is None:
    print('G868 header NOT FOUND - nothing to do')
    sys.exit(0)
print('G868 header at line:', idx + 1)
# trim trailing blank lines before G868
end = idx
while end > 0 and lines[end-1].strip() == '':
    end -= 1
print('truncate to line:', end)
bak = p + '.bak_before_g868_rollback'
open(bak, 'w', encoding='utf-8').writelines(lines)
print('backup written:', bak)
open(p, 'w', encoding='utf-8').writelines(lines[:end])
print('AFTER total lines:', end)
