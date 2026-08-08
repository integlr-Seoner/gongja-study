"""Step C-2: koatrinputlegend.ini 전수 파싱

구조 (실측):
  각 TR 블록이 [OPT***** : 설명] 형식의 헤더로 시작
  그 아래 '필드이름=설명' 라인들
  '종목코드=시세별 종목코드 (KRX:..., NXT:..._NX, 통합:..._AL)' 같은 형식

목적:
  1. 전체 TR 목록 나열
  2. 각 TR이 NXT를 지원하는지 판정 (종목코드 필드에 NXT 명시 여부)
  3. 특히 OPT10080 (분봉), OPT10081 (일봉), OPT10004 (호가) 등 확정
  4. NXT 거래가능 종목 리스트 조회 TR 존재 여부
"""
import re

P = r'C:\OpenAPI\koatrinputlegend.ini'
text = open(P, encoding='euc-kr').read()

# TR 블록 헤더 패턴: [OPT***** : 이름] 또는 [OPW***** : 이름]
header_re = re.compile(r'\[(OP[TW]?\w{5,6}|opt\w{5,6})\s*:\s*([^\]]+)\]')
headers = [(m.start(), m.group(1).strip(), m.group(2).strip())
           for m in header_re.finditer(text)]

print(f'총 TR 블록: {len(headers)}개')
print()

# 각 블록의 본문 추출 + NXT 지원 판정
nxt_supported = []
nxt_none = []
for i, (pos, code, name) in enumerate(headers):
    end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
    body = text[pos:end]
    has_nxt = ('_NX' in body) or ('NXT' in body)
    if has_nxt:
        nxt_supported.append((code, name, body))
    else:
        nxt_none.append((code, name))

print(f'NXT 지원 TR: {len(nxt_supported)}개')
print(f'NXT 미지원 TR: {len(nxt_none)}개')
print()

print('=' * 70)
print('NXT 지원 TR 목록')
print('=' * 70)
for code, name, _ in nxt_supported:
    print(f'  {code} : {name}')

print()
print('=' * 70)
print('NXT 미지원 TR 목록 (참고)')
print('=' * 70)
for code, name in nxt_none:
    print(f'  {code} : {name}')
