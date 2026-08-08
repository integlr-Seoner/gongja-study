# -*- coding: utf-8 -*-
"""검증 2종을 한 번에 실행하고 요약만 출력한다.

    python D:\\StockAnalyst\\book_extracts\\_verify.py

- 환경변수 접두어(PYTHONIOENCODING=...)와 파이프(| grep)가 필요 없다.
  둘 다 권한 규칙 `Bash(python:*)` 매칭을 깨뜨리므로 스크립트 안에서 처리한다.
- 옵션 없이 실행하면 spine + 참조(--also-handover) 요약을 출력한다.
"""
import os
import re
import subprocess
import sys

BASE = r'D:\StockAnalyst\book_extracts'
PY = sys.executable
KEEP = re.compile(r'COMBINED|OVER|DANGLING|RESULT|중복 정의|참조 총수|최대 정의|신규 헤더')


def run(args, title):
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run([PY] + args, cwd=BASE, env=env,
                       capture_output=True, text=True, encoding='utf-8')
    out = (p.stdout or '') + (p.stderr or '')
    print('--- %s ---' % title)
    for line in out.split('\n'):
        if KEEP.search(line):
            print(line.rstrip())
    return p.returncode, out


def main():
    extra = sys.argv[1] if len(sys.argv) > 1 else None

    rc1, o1 = run(['_check_gspine.py'], 'spine')
    args = ['_check_grefs.py', '--also-handover']
    if extra:
        args = ['_check_grefs.py', '--extra', extra]
    rc2, o2 = run(args, '참조' + (' (--extra)' if extra else ' (핸드오버 포함)'))

    ok = 'RESULT: OK' in o1 and 'RESULT: OK' in o2
    print()
    print('=> %s' % ('전부 통과' if ok else '!! 실패 항목 있음 - 위 출력 확인'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
