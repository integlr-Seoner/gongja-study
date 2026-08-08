# -*- coding: utf-8 -*-
"""재료 엑셀(2부) 실측 거래대금 vs 정독 노트의 육안 판독/적정거래대금 대조"""
import os, sys, io
sys.path.insert(0, r'D:\StockAnalyst\book_extracts')
from _parse_jaeryo import parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 정독 노트에 기록된 저자 제시 적정거래대금 (억) — G-spine 근거
JEONGJEONG = {
    '휴마시스': None, '신풍 (前 신풍제지)': None, '맥스트': 4000,
    '서울옥션': None, '승일': None, '두산에너빌리티 (前 두산중공업)': None,
    '한국파마': None, '바이오로그디바이스': None, '엠게임': None,
    '갤럭시아에스엠': None, '폴라리스오피스 (前 인프라웨어)': None,
    '세종메디칼': None, '한전기술': None, '효성오앤비': None, '웹스': None,
    '아이비김영': None, '위지윅스튜디오': None,
    '네오위즈': 2200, '삼아알미늄': 1350, '제주반도체': 2100, 'KEC': 1800,
    '비트나인': 1300, 'FSN': 1000, '램테크놀러지': 1800, '이노뎁': 1200,
    '와이제이엠게임즈': 1700, '인성정보': 800, '이씨에스': 1000,
    '이수앱지스': 2000, '엑세스바이오': 3600,
}

title, stocks = parse('2부')
print('%-28s %6s %8s %8s %8s %8s  %s' % ('종목', 'n', '최소', '중앙', '최대', '적정', '적정 대비 최대'))
print('-' * 100)
for name, recs in stocks:
    vals = sorted(v[0] for t, d, v in recs if t == 'REC' and isinstance(v[0], (int, float)))
    if not vals:
        print('%-28s %6d  (거래대금 수치 없음)' % (name, 0)); continue
    med = vals[len(vals)//2]
    adj = JEONGJEONG.get(name)
    ratio = ('x%.2f' % (vals[-1]/adj)) if adj else '-'
    print('%-28s %6d %8d %8d %8d %8s  %s'
          % (name, len(vals), vals[0], med, vals[-1], adj if adj else '-', ratio))
