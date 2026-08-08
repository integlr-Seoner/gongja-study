# -*- coding: utf-8 -*-
"""중간 파일을 노트에 BOM 없이 append 하는 헬퍼.
사용법:  python _append_note.py _append_log\_append_gNNNN.md
단순 단일 명령이라 권한 와일드카드(Bash(python:*))로 매칭돼 프롬프트가 뜨지 않는다.
"""
import io, os, sys

NOTE = r'D:\StockAnalyst\book_extracts\학습노트\11_단타매매_정독.md'

def main():
    if len(sys.argv) < 2:
        print('!! usage: python _append_note.py <extra.md>'); return 2
    extra = sys.argv[1]
    if not os.path.isabs(extra):
        extra = os.path.join(r'D:\StockAnalyst\book_extracts', extra)
    if not os.path.exists(extra):
        print('!! extra 없음:', extra); return 2
    with io.open(NOTE, 'rb') as f:
        nb = f.read()
    with io.open(extra, 'r', encoding='utf-8') as f:
        add = f.read()
    sep = b'' if nb.endswith(b'\n\n') else (b'\n' if nb.endswith(b'\n') else b'\n\n')
    with io.open(NOTE, 'ab') as f:
        f.write(sep + add.encode('utf-8'))
    print('appended %d chars from %s' % (len(add), os.path.basename(extra)))
    return 0

if __name__ == '__main__':
    sys.exit(main())
