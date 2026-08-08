# -*- coding: utf-8 -*-
"""44차 미결 가설 4건 일괄 검정 (엑셀만으로 산출 가능)"""
import os, sys, io, re
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import statistics as st
from datetime import datetime

def waves_of(recs):
    """WAVE 구분자로 분절. 반환 = [[rec,...], ...] (마지막 파동 포함)"""
    ws, cur = [], []
    for t, d, v in recs:
        if t == 'WAVE':
            if cur: ws.append(cur)
            cur = []
        else:
            cur.append((d, v[0], ('' if v[1] is None else str(v[1])).strip()))
    if cur: ws.append(cur)
    return ws

ALL = []
for part in ['1부', '2부', '3부']:
    _, stocks = parse(part)
    for name, recs in stocks:
        for wi, w in enumerate(waves_of(recs), 1):
            ALL.append((part, name, wi, w))

print('총 파동 수: %d' % len(ALL))
print('파동 길이 분포: min=%d med=%.0f max=%d' %
      (min(len(w) for *_, w in ALL), st.median([len(w) for *_, w in ALL]), max(len(w) for *_, w in ALL)))
print()

# ── ① 파동 내 최대 거래대금의 상대 위치 ──────────────────────────
print('=' * 78)
print('① 가설: 파동 종료 = 최대 거래대금 (G954 신풍제약·G953 수젠텍)')
pos = []
for part, name, wi, w in ALL:
    vals = [(i, a) for i, (d, a, s) in enumerate(w) if isinstance(a, (int, float))]
    if len(vals) < 3: continue
    mi = max(vals, key=lambda x: x[1])[0]
    pos.append(mi / (len(w) - 1))
print('  대상 파동 %d개(길이 3+ / 거래대금 有)' % len(pos))
print('  최대 거래대금의 상대 위치(0=파동 시작, 1=파동 끝):')
print('    min=%.2f  Q1=%.2f  중앙=%.2f  Q3=%.2f  max=%.2f  평균=%.2f'
      % (min(pos), st.quantiles(pos, n=4)[0], st.median(pos),
         st.quantiles(pos, n=4)[2], max(pos), st.mean(pos)))
print('    후반부(≥0.5) 비율: %.1f%%   최후미(=1.0) 비율: %.1f%%'
      % (100*sum(1 for p in pos if p >= .5)/len(pos), 100*sum(1 for p in pos if p == 1.0)/len(pos)))
print('    ※무작위면 평균 0.50, 최후미 비율 ≈ 1/평균길이')

# ── ② 재료 없음("-")의 파동 내 상대 위치 ────────────────────────
print('=' * 78)
print('② 가설: 재료 없음이 파동 말미에 몰림 (G961 위메이드맥스)')
epos, other = [], []
for part, name, wi, w in ALL:
    if len(w) < 3: continue
    for i, (d, a, s) in enumerate(w):
        (epos if s in ('', '-') else other).append(i / (len(w) - 1))
print('  재료 없음 %d건 / 재료 있음 %d건 (길이 3+ 파동 내)' % (len(epos), len(other)))
print('  재료 없음 위치 : 중앙=%.2f  평균=%.2f  후반부(≥0.5) 비율=%.1f%%'
      % (st.median(epos), st.mean(epos), 100*sum(1 for p in epos if p >= .5)/len(epos)))
print('  재료 있음 위치 : 중앙=%.2f  평균=%.2f  후반부(≥0.5) 비율=%.1f%%'
      % (st.median(other), st.mean(other), 100*sum(1 for p in other if p >= .5)/len(other)))

# ── ③ 의문형 헤드라인의 파동 내 위치 ────────────────────────────
print('=' * 78)
print('③ 가설: 의문·불확실 헤드라인 = 파동 후반부 (G953·G954·G965)')
Q = re.compile(r'(\?|까\.|까\?|까$|될까|할까|오를까|하나\.|하나\?|나\.\.|시선도|우려)')
qpos, npos = [], []
for part, name, wi, w in ALL:
    if len(w) < 3: continue
    for i, (d, a, s) in enumerate(w):
        if s in ('', '-'): continue
        (qpos if Q.search(s) else npos).append(i / (len(w) - 1))
print('  의문형 %d건 / 평서형 %d건' % (len(qpos), len(npos)))
if qpos:
    print('  의문형 위치 : 중앙=%.2f  평균=%.2f  후반부(≥0.5) 비율=%.1f%%'
          % (st.median(qpos), st.mean(qpos), 100*sum(1 for p in qpos if p >= .5)/len(qpos)))
print('  평서형 위치 : 중앙=%.2f  평균=%.2f  후반부(≥0.5) 비율=%.1f%%'
      % (st.median(npos), st.mean(npos), 100*sum(1 for p in npos if p >= .5)/len(npos)))

# ── ④ 재료 D+1 / D+0 거래대금 비율 ──────────────────────────────
print('=' * 78)
print('④ 가설: 재료 1일차 ≠ 거래대금 급증일 (G953 수젠텍 14배·G963 엔케이맥스 15배)')
ratios = []
for part, name, wi, w in ALL:
    for i in range(len(w) - 1):
        d0, a0, s0 = w[i]; d1, a1, s1 = w[i+1]
        if not (isinstance(a0, (int, float)) and isinstance(a1, (int, float))): continue
        if a0 <= 0: continue
        gap = (d1 - d0).days
        if gap < 1 or gap > 3: continue          # 연속 거래일(주말 포함)
        if s0 in ('', '-') or s1 in ('', '-'): continue
        # 동일 재료 판정: 뒷날 텍스트에 '지속'/'이틀째' 또는 앞날 핵심어 반복
        same = ('지속' in s1) or ('이틀째' in s1) or ('재부각' in s1)
        ratios.append((a1 / a0, same, part, name, d0.date(), a0, a1, s0[:36], s1[:36]))
print('  연속 거래일 쌍 %d건 (양일 모두 재료 有)' % len(ratios))
r_all = [r[0] for r in ratios]
r_same = [r[0] for r in ratios if r[1]]
print('  D+1/D+0 전체 : 중앙=%.2f  평균=%.2f  >1 비율=%.1f%%'
      % (st.median(r_all), st.mean(r_all), 100*sum(1 for r in r_all if r > 1)/len(r_all)))
if r_same:
    print('  ★동일 재료 지속(%d건) : 중앙=%.2f  평균=%.2f  >1 비율=%.1f%%'
          % (len(r_same), st.median(r_same), st.mean(r_same), 100*sum(1 for r in r_same if r > 1)/len(r_same)))
print('  ★D+1이 D+0의 3배 이상인 사례 상위 8:')
print('  ※★열 라벨 주의: [D+0 재료]와 [D+1 재료]를 반드시 구분할 것 (44차 G984·G986 오독 원인)')
for r, same, part, name, d, a0, a1, s0, s1 in sorted(ratios, reverse=True)[:8]:
    print('    x%.1f  [%s] %-20s %s' % (r, part, name, d))
    print('           D+0 %5d억 | %s' % (a0, s0))
    print('           D+1 %5d억 | %s' % (a1, s1))
