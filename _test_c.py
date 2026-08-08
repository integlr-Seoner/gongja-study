# -*- coding: utf-8 -*-
"""ⓒ 파동 구분 기준 = 적정거래대금 발생 여부? + 밴드 폭 ↔ α 관계"""
import io, sys
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
from _alpha_v2 import ADJ1, ADJ2, mid, prank
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statistics as st

def waves_of(recs):
    ws, cur = [], []
    for t, d, v in recs:
        if t == 'WAVE':
            if cur: ws.append(cur); cur = []
        else:
            cur.append((d, v[0]))
    if cur: ws.append(cur)
    return ws

print('=' * 80)
print('ⓒ 41차 G881 판정 검정: "파동 구분 기준 = 적정거래대금 발생 여부"')
print('   → 각 파동이 적정거래대금 이상 레코드를 포함하는가?')
hit = tot = 0
zero_waves = []
for part, ADJ in [('1부', ADJ1), ('2부', ADJ2)]:
    _, stocks = parse(part)
    for name, recs in stocks:
        key = next((k for k in ADJ if name.startswith(k)), None)
        if key is None: continue
        a = mid(ADJ[key])
        for wi, w in enumerate(waves_of(recs), 1):
            vals = [x for _, x in w if isinstance(x, (int, float))]
            if not vals: continue
            tot += 1
            if max(vals) >= a: hit += 1
            else: zero_waves.append((part, key, wi, len(vals), max(vals), a))
print('  전체 파동 %d개 중 적정거래대금 이상을 포함한 파동: %d개 (%.1f%%)' % (tot, hit, 100*hit/tot))
print('  ★적정거래대금 미달 파동: %d개 (%.1f%%)' % (len(zero_waves), 100*len(zero_waves)/tot))
for p, k, wi, n, mx, a in zero_waves[:14]:
    print('     [%s] %-16s %d파동 n=%2d | 최대 %5d억 < 적정 %5d억 (%.0f%%)' % (p, k, wi, n, mx, a, 100*mx/a))

print()
print('=' * 80)
print('G943/G987 가설 검정: "밴드 폭이 좁은 종목은 α가 높다"')
rows = []
for part, ADJ in [('1부', ADJ1), ('2부', ADJ2)]:
    _, stocks = parse(part)
    for name, recs in stocks:
        key = next((k for k in ADJ if name.startswith(k)), None)
        if key is None: continue
        v = ADJ[key]
        if not isinstance(v, tuple): continue          # 단일값 = 밴드 없음
        width = v[1] / v[0]                            # 밴드 폭 배수
        vals = sorted(x[0] for t, d, x in recs if t == 'REC' and isinstance(x[0], (int, float)))
        if len(vals) < 4: continue
        rows.append((width, prank(vals, mid(v)), part, key, v))
rows.sort()
print('  밴드 제시 종목 %d개 (단일값 종목은 제외)' % len(rows))
print('  %-18s %-6s %-10s %s' % ('종목', '밴드폭', 'α', '밴드'))
for w, a, part, k, v in rows:
    print('   [%s] %-14s x%.2f   %3.0f%%   %d~%d억' % (part, k, w, a*100, v[0], v[1]))
if len(rows) >= 4:
    ws = [r[0] for r in rows]; as_ = [r[1] for r in rows]
    n = len(rows); half = n // 2
    print('  ★좁은 밴드(하위 %d) α 평균 = %.0f%%' % (half, 100*st.mean(as_[:half])))
    print('  ★넓은 밴드(상위 %d) α 평균 = %.0f%%' % (n-half, 100*st.mean(as_[half:])))
