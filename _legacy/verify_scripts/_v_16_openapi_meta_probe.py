"""Step C-1: C:\\OpenAPI 메타 파일 NXT 관련 내용 실측"""
import os, re

FILES = ['apiinitrsc.lst', 'apiotrsc.lst', 'koascreentrmap.ini',
         'koatrinputlegend.ini', 'mst.lst']

def probe(fn):
    p = os.path.join(r'C:\OpenAPI', fn)
    raw = open(p, 'rb').read()
    text = None
    used_enc = None
    for enc in ['euc-kr', 'utf-8', 'cp949']:
        try:
            text = raw.decode(enc)
            used_enc = enc
            break
        except Exception:
            continue
    if text is None:
        return fn, len(raw), 'BIN', 0, repr(raw[:80])
    # NXT 관련 키워드 히트
    patterns = [r'NXT', r'_NX', r'_AL', r'nxt', '대체거래', '넥스트']
    total_hits = 0
    per_pat = {}
    for pat in patterns:
        hits = len(re.findall(pat, text))
        per_pat[pat] = hits
        total_hits += hits
    head = text[:120].replace('\r', '').replace('\n', '|')
    return fn, len(raw), used_enc, total_hits, per_pat, head

for f in FILES:
    r = probe(f)
    print('---', f, '---')
    print(f'  size={r[1]}, enc={r[2]}, total NXT hits={r[3]}')
    if isinstance(r[4], dict):
        print(f'  per pattern: {r[4]}')
    print(f'  head: {r[5]}')
    print()
