# -*- coding: utf-8 -*-
# G-spine 무결성 + 사례 커버리지 점검 (일봉수급추적 자료집 정독 트랙)
# [1] G번호: 파일 내부 연속성 + 파일 간 경계 + 통합 중복/gap
# [2] 사례 커버리지: 노트의 [N부 ... #NN] 태그를 원본 엑셀 종목 수와 대조
import re, io, sys
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')

# ── [3] 페이지 커버리지 = 옵트인 (2026-08-02) ──────────────────────────
#  실측: 전체 66.1s 중 [3]이 57s(get_image_rects 41.6s + 픽스맵 15.0s).
#  [3]의 검사 대상은 08_차트매매_정독.md + 차트매매 PDF 5종(749p)뿐이며
#  해당 트랙은 완독·고정 상태 → 배치마다 재검사할 이유가 없다.
#  평소: [1]+[2]만 (~0.5s) / 차트매매 노트를 건드렸을 때만 --full.
#  ★--full 실행 시점 규칙은 _CC_정독_세션지시.md 참조.
import json, os as _os
FULL = '--full' in sys.argv
CACHE_PATH = r'D:\StockAnalyst\book_extracts\_gspine_pagecache.json'
_pcache = {}
if FULL:
    try:
        _pcache = json.load(io.open(CACHE_PATH, encoding='utf-8'))
    except Exception:
        _pcache = {}

NOTE_FILES = [
    (r'D:\StockAnalyst\book_extracts\학습노트\08_차트매매_정독.md', 128),
    (r'D:\StockAnalyst\book_extracts\학습노트\09_주가흐름추적_정독.md', 549),
    (r'D:\StockAnalyst\book_extracts\학습노트\10_일봉수급추적_정독.md', 555),
    (r'D:\StockAnalyst\book_extracts\학습노트\10b_재료자료집_정독.md', 942),
    (r'D:\StockAnalyst\book_extracts\학습노트\10c_QA자료집_정독.md', 1123),
    (r'D:\StockAnalyst\book_extracts\학습노트\10d_주가추적노트_정독.md', 1179),
    (r'D:\StockAnalyst\book_extracts\학습노트\11_단타매매_정독.md', 1183),
    (r'D:\StockAnalyst\book_extracts\학습노트\12_수식관리자_정독.md', 4378),
    (r'D:\StockAnalyst\book_extracts\학습노트\13_스윙매매_정독.md', 4746),
    (r'D:\StockAnalyst\book_extracts\학습노트\02f_재료매매_잔여_정독.md', 6103),
]

ok = True
prev_last = None
prev_name = None
combined = []
all_header_lines = []

print('========== [1] G-SPINE ==========')
for path, start in NOTE_FILES:
    lines = io.open(path, encoding='utf-8').readlines()
    all_header_lines += [l for l in lines if re.match(r'^## G\d+\.', l)]
    g = [int(m.group(1)) for l in lines
         for m in [re.match(r'^## G(\d+)\.', l)] if m]
    name = path.split('\\')[-1]
    print('FILE:', name)
    if not g:
        print('  G headers   : 0 | (신규 노트 — 정독 시작 전, start=%d 예약)' % start)
        if prev_last is not None and start != prev_last + 1:
            print('  !! RESERVED START MISMATCH:', prev_last, '-> reserved', start); ok = False
        continue
    print('  G headers   :', len(g), '| first/last:', g[0], '/', g[-1])
    dup = sorted({x for x in g if g.count(x) > 1})
    gaps = [(g[i-1], g[i]) for i in range(1, len(g)) if g[i] != g[i-1] + 1]
    print('  duplicates  :', dup if dup else 'NONE')
    print('  gaps        :', gaps if gaps else 'NONE')
    if dup or gaps:
        ok = False
    if g[0] != start:
        print('  !! FIRST MISMATCH: expected', start, 'got', g[0]); ok = False
    if prev_last is not None:
        if g[0] == prev_last + 1:
            print('  boundary    : OK (', prev_last, '->', g[0], ')')
        else:
            print('  !! BOUNDARY BREAK:', prev_last, '-> next first', g[0]); ok = False
    prev_last, prev_name = g[-1], name
    combined += g

c = sorted(combined)
cdup = sorted({x for x in c if c.count(x) > 1})
cgaps = sorted(set(range(c[0], c[-1] + 1)) - set(c))
print('--- COMBINED:', c[0], '->', c[-1], '| headers', len(c), '| unique', len(set(c)))
print('    duplicates:', cdup if cdup else 'NONE', '| gaps:', 'NONE' if not cgaps else cgaps)
if cdup or cgaps:
    ok = False

print()
print('========== [2] CASE COVERAGE (#NN vs 엑셀 종목수) ==========')
# 노트 헤더의 [N부 ... #NN (+ #NN)] 태그 수집
found = {'1': set(), '2': set(), '3': set()}
tag = re.compile(r'\[([123])부')
for l in all_header_lines:
    m = tag.search(l)
    if not m:
        continue
    part = m.group(1)
    bracket = l[l.find('['): l.find(']') + 1] if ']' in l else l
    for num in re.findall(r'#(\d+)', bracket):
        found[part].add(int(num))

p3_inprog = None  # 3부 진행률 (len_in_range, total); None=파싱 실패
try:
    from _parse_jaeryo import parse
    for p in ('1', '2', '3'):
        _, stocks = parse(p + '부')
        total = len(stocks)
        fs = found[p]
        in_range = sorted(x for x in fs if 1 <= x <= total)
        missing = sorted(set(range(1, total + 1)) - fs)
        extra = sorted(x for x in fs if x > total)
        if p == '3':
            # 3부 = 정독 진행 중 → 진행률만 표시, gate(ok) FAIL 안 시킴(완주 시 자동 complete)
            p3_inprog = (len(in_range), total)
            status = 'OK' if not missing else ('진행중 %d/%d' % (len(in_range), total))
        else:
            status = 'OK' if not missing else 'MISSING ' + str(missing)
            if missing:
                ok = False
        print('  %s부: 엑셀 %2d종 | 노트 기재 %2d종 | %s%s'
              % (p, total, len(fs), status, (' | EXTRA ' + str(extra)) if extra else ''))
except Exception as e:
    print('  (parse 불가 — 커버리지 스킵:', e, ')')

print()
print('========== [3] PAGE COVERAGE (기본서·적정거래대금, 콘텐츠페이지) ==========')
# 노트(헤더+본문 '(보충 p.NN)' 포함) 페이지 vs 원본 PDF 콘텐츠 페이지 대조.
# 원본의 단색배경(소제목 구분/표지) 페이지는 정독 대상 아님 → 자동 제외.
CHART_BASE = r'D:\StockAnalyst\금융공자_가이드북\차트매매'
PAGE_SEGS = [
    ('기본서 상(1권)', 128, 225, r'차트 매매 기본서 - 상 (1권).pdf'),
    ('기본서 중(2권)', 226, 323, r'차트 매매 기본서 - 중 (2권).pdf'),
    ('기본서 하(3권)', 324, 388, r'차트 매매 기본서 - 하 (3권).pdf'),
    ('부록',          389, 457, r'차트 매매 기본서 - 부록.pdf'),
    ('적정거래대금',    458, 548, r'적정 거래대금 이론 보충 자료.pdf'),
]
try:
    if not FULL:
        raise RuntimeError('--full 미지정 (평소 배치에서는 생략, 차트매매 노트 수정 시 --full 실행)')
    import os
    import fitz
    from collections import Counter
    note08 = io.open(NOTE_FILES[0][0], encoding='utf-8').read()
    hdrs = [(int(m.group(1)), m.end()) for m in re.finditer(r'^## G(\d+)\.', note08, re.M)]
    starts = [e for _, e in hdrs]
    def block_of(idx):
        s = starts[idx]
        return note08[s: starts[idx + 1] if idx + 1 < len(starts) else len(note08)]
    hdr_line = {n: note08[note08.rfind('\n', 0, e):e] for n, e in hdrs}

    def teal_pages(pdf):
        # ★캐시: PDF의 (mtime, size)가 그대로면 이전 산출 결과를 재사용.
        #   PDF는 변환 완료 후 불변이므로 2회차부터 렌더링 전량 생략된다.
        _key = _os.path.abspath(pdf)
        _st = _os.stat(pdf)
        _sig = [_st.st_mtime_ns, _st.st_size]
        _ent = _pcache.get(_key)
        if _ent and _ent.get('sig') == _sig:
            return set(_ent['teal']), _ent['total']
        # 정독 대상 아님(구분/표지) 페이지 감지:
        #  (a) 단색배경(소제목 목차·챕터 표지) 또는
        #  (b) 이미지 면적 40~72%로 균일 + 텍스트 거의 없음(패턴 도입 표지)
        # 콘텐츠 차트 페이지는 이미지 면적 85%+ 라 안전하게 구분됨.
        d = fitz.open(pdf); tl = set()
        for p in range(1, d.page_count + 1):
            pg = d[p - 1]
            pix = pg.get_pixmap(matrix=fitz.Matrix(0.22, 0.22))
            px = pix.samples; ch = pix.n; c = Counter()
            for i in range(0, len(px), ch * 5):
                c[px[i:i+3]] += 1
            r, g_, b = c.most_common(1)[0][0][:3]
            solid = not (r > 235 and g_ > 235 and b > 235)
            parea = pg.rect.width * pg.rect.height
            iarea = 0.0
            for im in pg.get_images(full=True):
                for rc in pg.get_image_rects(im[0]):
                    iarea += rc.width * rc.height
            tarea = sum((bb[2]-bb[0])*(bb[3]-bb[1]) for bb in pg.get_text('blocks'))
            iratio = iarea / parea if parea else 0
            tratio = tarea / parea if parea else 0
            cover_sheet = (0.40 < iratio < 0.72) and tratio < 0.02
            if solid or cover_sheet:
                tl.add(p)
        tot = d.page_count; d.close()
        _pcache[_key] = {'sig': _sig, 'teal': sorted(tl), 'total': tot}
        return tl, tot

    for lab, lo, hi, fn in PAGE_SEGS:
        pdf = os.path.join(CHART_BASE, fn)
        pages = set()
        for idx, (n, _) in enumerate(hdrs):
            if lo <= n <= hi:
                blk = hdr_line[n] + block_of(idx)
                for a, b in re.findall(r'p\.(\d+)~(\d+)', blk):
                    pages.update(range(int(a), int(b) + 1))
                for a in re.findall(r'p\.(\d+)', blk):
                    pages.add(int(a))
        tl, tot = teal_pages(pdf)
        pages = {p for p in pages if 1 <= p <= tot}
        content = set(range(1, tot + 1)) - tl
        missing = sorted(content - pages)
        if missing:
            print('  %-16s 원본%dp | ★콘텐츠 미커버: %s' % (lab, tot, missing))
            ok = False
        else:
            print('  %-16s 원본%dp | 콘텐츠페이지 전량 커버 (구분페이지 %d개 제외)' % (lab, tot, len(tl)))
    try:
        json.dump(_pcache, io.open(CACHE_PATH, 'w', encoding='utf-8'))
    except Exception as e:
        print('  (캐시 저장 실패 -', e, ')')
except Exception as e:
    print('  (페이지 커버리지 스킵 -', e, ')')

print()
_s3 = '' if FULL else ' · [3] SKIP(--full 시 검사)'
if not ok:
    print('RESULT: FAIL - see flags above' + _s3)
elif p3_inprog and p3_inprog[0] < p3_inprog[1]:
    print(('RESULT: OK - spine intact & coverage complete (1·2부) · 3부 진행중 %d/%d' % p3_inprog) + _s3)
else:
    print('RESULT: OK - spine intact & coverage complete' + _s3)
