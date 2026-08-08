# -*- coding: utf-8 -*-
"""배치 1건을 단일 명령으로 처리한다.

    python D:\\StockAnalyst\\book_extracts\\_batch.py 2260

절차: ①참조 검증(--extra) → OK일 때만 ②노트 append → ③spine 검증
- 어느 단계든 실패하면 즉시 중단하고 이후 단계를 실행하지 않는다.
- cd / export / 파이프가 없는 단일 명령이라 권한 규칙 `Bash(python:*)` 가
  안정적으로 매칭된다(복합 명령은 매칭이 불안정하다).
"""
import os
import subprocess
import sys

BASE = r'D:\StockAnalyst\book_extracts'
PY = sys.executable


def run(args, title):
    print('\n' + '=' * 60)
    print('[%s] %s' % (title, ' '.join(os.path.basename(a) for a in args[1:3])))
    print('=' * 60)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    p = subprocess.run(args, cwd=BASE, env=env,
                       capture_output=True, text=True, encoding='utf-8')
    out = (p.stdout or '') + (p.stderr or '')
    print(out.rstrip())
    return p.returncode, out


def main():
    if len(sys.argv) < 2:
        print('!! usage: python _batch.py <첫G번호>   예) python _batch.py 2260')
        return 2
    g = sys.argv[1].lstrip('Gg')
    extra = os.path.join(BASE, '_append_log', '_append_g%s.md' % g)
    if not os.path.exists(extra):
        print('!! 중간 파일 없음:', extra)
        return 2

    rc, out = run([PY, '_check_grefs.py', '--extra', extra], '1/3 참조 검증')
    if rc != 0 or 'RESULT: OK' not in out:
        print('\n!! 참조 검증 실패 - append 하지 않고 중단')
        return 1

    rc, _ = run([PY, '_append_note.py', extra], '2/3 노트 append')
    if rc != 0:
        print('\n!! append 실패')
        return 1

    rc, out = run([PY, '_check_gspine.py'], '3/3 spine 검증')
    if rc != 0 or 'RESULT: OK' not in out:
        print('\n!! spine 검증 실패 - 즉시 확인 필요')
        return 1

    print('\n' + '=' * 60)
    print('배치 완료 - 3단계 전부 통과')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
