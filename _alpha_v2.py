# -*- coding: utf-8 -*-
"""ⓐ+ⓑ: 적정거래대금 60종 전수 + 쩜상 제외 → α 재산출"""
import io, sys
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
import statistics as st

# 정독 노트(10_일봉수급추적_정독.md)에서 전수 추출. 밴드는 (하한,상한). 갱신형은 (초기,갱신) → 초기값 사용.
ADJ1 = {  # 1부
 'EDGC':1750,'유니온':900,'소프트캠프':470,'프리엠스':210,'수젠텍':1100,
 '신풍제약':(5000,6600),'현대바이오':(2600,2700),'GH신소재':1100,'진원생명과학':5000,
 '로보티즈':2000,'네오위즈홀딩스':420,'위메이드맥스':800,'경남스틸':1500,'엔케이맥스':900,
 '유바이오로직스':2100,'버킷스튜디오':(1800,1900),'바이오니아':2600,'한국주강':200,
 '티비씨':900,'형지I&C':(150,300),'형지엘리트':(950,1000),'SM C&C':2000,
 '갤럭시아머니트리':1100,'대원화성':1000,'에코캡':500,'나노씨엠에스':700,
 '포스코스틸리온':1600,'피제이메탈':850,'한화투자증권':3000,'위지트':1600,
}
ADJ2 = {  # 2부
 '휴마시스':2300,'신풍':(800,1400),'맥스트':4000,'서울옥션':500,'승일':360,
 '두산에너빌리티':7900,'한국파마':2200,'바이오로그디바이스':1000,'엠게임':(1500,1600),
 '갤럭시아에스엠':400,'폴라리스오피스':(400,1000),'세종메디칼':750,'한전기술':700,
 '효성오앤비':1000,'웹스':750,'아이비김영':800,'위지윅스튜디오':(1300,1550),
 '네오위즈':2200,'삼아알미늄':(1300,1400),'제주반도체':2100,'KEC':1800,'비트나인':1300,
 'FSN':1000,'램테크놀러지':1800,'이노뎁':1200,'와이제이엠게임즈':1700,'인성정보':800,
 '이씨에스':1000,'이수앱지스':2000,'엑세스바이오':3600,
}
JJEOM = 100  # 쩜상 판정 임계(억) — G986: <100억 10건 중 7건이 상한가/지속/연일 어휘

def mid(v): return sum(v)/2 if isinstance(v, tuple) else v
def prank(vals, x): return sum(1 for v in vals if v <= x) / len(vals)

def run(label, exclude_jjeom):
    rows = []
    for part, ADJ in [('1부', ADJ1), ('2부', ADJ2)]:
        _, stocks = parse(part)
        for name, recs in stocks:
            key = next((k for k in ADJ if name.startswith(k)), None)
            if key is None: continue
            vals = sorted(v[0] for t, d, v in recs
                          if t == 'REC' and isinstance(v[0], (int, float))
                          and not (exclude_jjeom and v[0] < JJEOM))
            if len(vals) < 4: continue
            a = mid(ADJ[key])
            rows.append((prank(vals, a), a/st.median(vals), part, key, len(vals)))
    prs = [r[0] for r in rows]; rs = [r[1] for r in rows]
    print('[%s] n=%d종' % (label, len(rows)))
    print('  α(분위수): min=%.0f%%  Q1=%.0f%%  중앙=%.0f%%  Q3=%.0f%%  max=%.0f%%  평균=%.0f%%'
          % (min(prs)*100, st.quantiles(prs,n=4)[0]*100, st.median(prs)*100,
             st.quantiles(prs,n=4)[2]*100, max(prs)*100, st.mean(prs)*100))
    print('  적정/med : min=%.2f  중앙=%.2f  max=%.2f  평균=%.2f'
          % (min(rs), st.median(rs), max(rs), st.mean(rs)))
    return rows

print_main = True
if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    print('=' * 84)
    r_in  = run('전체 60종 · 쩜상 포함', False)
    print()
    r_ex  = run('전체 60종 · ★쩜상(<100억) 제외', True)
    print('=' * 84)
    print('★부별 비교 (쩜상 제외 기준)')
    for p in ['1부', '2부']:
        sub = [r for r in r_ex if r[2] == p]
        print('  %s n=%d | α 중앙=%.0f%% 평균=%.0f%% | 적정/med 중앙=%.2f'
              % (p, len(sub), st.median([x[0] for x in sub])*100,
                 st.mean([x[0] for x in sub])*100, st.median([x[1] for x in sub])))
    print()
    print('★α 하위 5 / 상위 5 (쩜상 제외)')
    r_ex.sort()
    for r in r_ex[:5]:  print('   낮음 %-18s [%s] α=%3.0f%%  적정/med=%.2f  n=%d' % (r[3], r[2], r[0]*100, r[1], r[4]))
    for r in r_ex[-5:]: print('   높음 %-18s [%s] α=%3.0f%%  적정/med=%.2f  n=%d' % (r[3], r[2], r[0]*100, r[1], r[4]))
