# -*- coding: utf-8 -*-
# G 교차참조 무결성 점검 — 노트 본문의 G번호 참조가 실재하는 헤더를 가리키는지 검사
#
# 기존 _check_gspine.py 는 수정하지 않는다(헤더 연속성·커버리지 전담).
# 본 스크립트는 '참조 무결성'만 전담한다.
#
# 사용법
#   python _check_grefs.py                      # 코퍼스 11개 파일 점검
#   python _check_grefs.py --extra <경로> ...    # append 예정 파일을 사전 점검
#   python _check_grefs.py --also-handover      # 마스터 핸드오버까지 점검
#
# 판정 기준 (임의 수치 없음)
#   정의 = '^## G(\d+)\.'  (_check_gspine.py 와 동일 정규식)
#   참조 = 본문 중 '\bG(\d+)\b' (헤더의 자기 번호는 제외)
#   OVER    : 참조 번호 > 코퍼스 최대값        → 존재 불가, 무조건 오류
#   DANGLING: 최대값 이하이나 정의 집합에 없음  → 결번 참조
import re, io, os, sys

NOTE_DIR = r'D:\StockAnalyst\book_extracts\학습노트'

# 정의 파일 = G헤더 보유 노트. 백업(*BAK*)은 중복 정의를 만들므로 제외.
CORPUS = [
    '02b_금융공자_보강.md',       # G1~23
    '02c_금융공자_2권보강.md',    # G24~52
    '02d_금융공자_3권보강.md',    # G53~81
    '02e_금융공자_4권보강.md',    # G82~127
    '08_차트매매_정독.md',        # G128~548
    '09_주가흐름추적_정독.md',    # G549~554
    '10_일봉수급추적_정독.md',    # G555~941
    '10b_재료자료집_정독.md',     # G942~1122
    '10c_QA자료집_정독.md',       # G1123~1178
    '10d_주가추적노트_정독.md',   # G1179~1182
    '11_단타매매_정독.md',        # G1183~4377
    '12_수식관리자_정독.md',      # G4378~4745
    '13_스윙매매_정독.md',        # G4746~ (스윙 트랙)
]
HANDOVER = 'HANDOVER_가이드북_트랙정독.md'

HDR = re.compile(r'^## G(\d+)\.')
REF = re.compile(r'\bG(\d+)\b')


def read_lines(path):
    # utf-8-sig: BOM이 있으면 제거, 없으면 utf-8과 동일 동작
    # (BOM이 남으면 첫 줄 '## G...' 헤더 매칭이 빗나가 정의 누락 + 오탐 발생)
    return io.open(path, encoding='utf-8-sig').readlines()


def collect_defs(paths):
    """정의된 G번호 집합 + 번호별 소속 파일"""
    defined = {}
    for p in paths:
        for ln in read_lines(p):
            m = HDR.match(ln)
            if m:
                n = int(m.group(1))
                defined.setdefault(n, []).append(os.path.basename(p))
    return defined


def collect_refs(paths):
    """참조 목록 [(파일, 줄번호, 참조번호, 줄내용)] — 헤더의 자기 번호는 제외"""
    refs = []
    for p in paths:
        name = os.path.basename(p)
        for i, ln in enumerate(read_lines(p), 1):
            body = ln
            m = HDR.match(ln)
            if m:
                body = ln[m.end():]  # 헤더의 자기 번호만 잘라내고 나머지는 검사
            for r in REF.finditer(body):
                refs.append((name, i, int(r.group(1)), ln.rstrip()))
    return refs


def main():
    args = sys.argv[1:]
    extras = []
    if '--extra' in args:
        i = args.index('--extra')
        for a in args[i + 1:]:
            if a.startswith('--'):
                break
            extras.append(a if os.path.isabs(a) else os.path.abspath(a))

    corpus = [os.path.join(NOTE_DIR, f) for f in CORPUS]
    missing = [p for p in corpus if not os.path.exists(p)]
    if missing:
        print('!! 코퍼스 파일 없음:', missing)
        return 2

    defined = collect_defs(corpus)
    maxg = max(defined)
    print('========== [1] 정의 집합 ==========')
    print('  정의 파일 : %d개' % len(corpus))
    print('  G 정의    : %d개 | 범위 %d ~ %d' % (len(defined), min(defined), maxg))
    dup = sorted(n for n, fs in defined.items() if len(fs) > 1)
    print('  중복 정의 :', dup if dup else 'NONE')

    # extra 파일의 신규 헤더는 정의로 인정 (append 예정분 사전 검증)
    if extras:
        for p in extras:
            if not os.path.exists(p):
                print('!! --extra 파일 없음:', p)
                return 2
        ex_def = collect_defs(extras)
        print('  --extra   : %s' % ', '.join(os.path.basename(p) for p in extras))
        print('              신규 헤더 %d개 %s' % (
            len(ex_def), ('(%d~%d)' % (min(ex_def), max(ex_def))) if ex_def else ''))
        for n, fs in ex_def.items():
            if n in defined:
                print('  !! 중복: G%d 이(가) 코퍼스에 이미 존재 (%s)' % (n, defined[n][0]))
        defined.update(ex_def)
        if ex_def:
            maxg = max(maxg, max(ex_def))

    targets = corpus + extras
    if '--also-handover' in args:
        targets = targets + [os.path.join(NOTE_DIR, HANDOVER)]

    refs = collect_refs(targets)
    over = [r for r in refs if r[2] > maxg]
    dangling = [r for r in refs if r[2] <= maxg and r[2] not in defined]

    print('\n========== [2] 참조 점검 ==========')
    print('  점검 파일 : %d개' % len(targets))
    print('  참조 총수 : %d' % len(refs))
    print('  최대 정의 : G%d' % maxg)

    # 라벨은 cp949 로 인코딩 가능한 문자만 쓴다.
    # (em-dash U+2014 등을 넣으면 PYTHONIOENCODING 미설정 콘솔에서 UnicodeEncodeError 로 죽는다)
    for label, items in (('OVER (최대값 초과, 존재 불가)', over),
                         ('DANGLING (결번 참조)', dangling)):
        print('\n  --- %s : %d건 ---' % (label, len(items)))
        for name, ln, n, text in items[:60]:
            print('   G%-6d %s L%d' % (n, name, ln))
            print('           %s' % text.strip()[:140])
        if len(items) > 60:
            print('   ... 외 %d건' % (len(items) - 60))

    ok = not over and not dangling and not dup
    print('\nRESULT: %s' % ('OK - 모든 G 참조가 실재 헤더를 가리킴' if ok else 'FAIL - 위 항목 확인 필요'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
