"""KRX Open API 실측 테스트
목적:
  1. KRX_OPEN_API_KEY 유효성 확인
  2. 기존 endpoint (KOSPI/KOSDAQ) 응답 확인
  3. NXT 추정 endpoint 탐색 (문서 없이 패턴 추정)

참고: base url = http://data-dbg.krx.co.kr/svc/apis
     알려진 endpoint: sto/stk_bydd_trd (KOSPI), sto/ksq_bydd_trd (KOSDAQ)

원칙:
  - 모든 호출은 실측 확인
  - 실패 시 에러 메시지 원문 기록
  - 추측하지 않음
"""
import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(0, r'D:\StockAnalyst')
load_dotenv(r'D:\StockAnalyst\.env')

API_KEY = os.getenv('KRX_OPEN_API_KEY', '')
BASE_URL = "http://data-dbg.krx.co.kr/svc/apis"

print(f'KRX_OPEN_API_KEY: {"있음" if API_KEY else "없음"}, 길이 {len(API_KEY)}')
print()


def call_endpoint(endpoint: str, params: dict = None, label: str = '') -> tuple:
    """endpoint 호출. (status, body_snippet, total_rows) 반환"""
    url = f"{BASE_URL}/{endpoint}"
    p = {'AUTH_KEY': API_KEY}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=20)
        status = r.status_code
        if status == 200:
            try:
                j = r.json()
                keys = list(j.keys())
                total_rows = 0
                for k in keys:
                    if isinstance(j[k], list):
                        total_rows += len(j[k])
                body = f'JSON keys={keys}, rows={total_rows}'
            except Exception as e:
                body = f'JSON parse error: {e} / body head: {r.text[:200]}'
                total_rows = 0
        else:
            body = r.text[:300]
            total_rows = 0
        return status, body, total_rows
    except Exception as e:
        return 0, f'Exception: {e}', 0


# === 단계 2-A: 알려진 endpoint (기본 동작 확인) ===
print('=' * 80)
print('단계 2-A: 알려진 endpoint 호출 테스트 (기준일 20260417)')
print('=' * 80)

test_date = '20260417'
known_endpoints = [
    ('sto/stk_bydd_trd', 'KOSPI 일별 시세'),
    ('sto/ksq_bydd_trd', 'KOSDAQ 일별 시세'),
    ('sto/knx_bydd_trd', 'KONEX 일별 시세 (추정)'),
]

for ep, label in known_endpoints:
    status, body, rows = call_endpoint(ep, {'basDd': test_date}, label)
    print(f'  [{ep}]')
    print(f'    {label}: status={status}, rows={rows}')
    print(f'    body: {body[:150]}')
    print()


# === 단계 2-B: NXT endpoint 패턴 추정 + 탐색 ===
print('=' * 80)
print('단계 2-B: NXT endpoint 존재 여부 탐색')
print('=' * 80)
print('  (401 = endpoint 존재하나 미신청, 404 = endpoint 자체 없음)')
print()

# 네이밍 패턴 추정: sto/{시장}_bydd_trd
# NXT 변형 가능성: nxt, ats, nxt_bydd_trd, ...
nxt_endpoint_guesses = [
    # NXT 직접
    ('sto/nxt_bydd_trd', 'NXT 일별 시세 (패턴1)'),
    ('sto/ats_bydd_trd', 'NXT ATS 일별 시세 (패턴2)'),
    # NXT + 시간외/프리
    ('sto/nxt_pre_bydd_trd', 'NXT 프리마켓 (패턴3)'),
    ('sto/nxt_aft_bydd_trd', 'NXT 애프터마켓 (패턴4)'),
    ('sto/nxt_main_bydd_trd', 'NXT 메인마켓 (패턴5)'),
    # 통합 시세
    ('sto/all_bydd_trd', 'KRX+NXT 통합 (패턴6)'),
    ('sto/uni_bydd_trd', '통합 시세 (패턴7)'),
    # KRX 확장
    ('sto/krx_bydd_trd', 'KRX 통합 (패턴8)'),
]

for ep, label in nxt_endpoint_guesses:
    status, body, rows = call_endpoint(ep, {'basDd': test_date}, label)
    marker = '🟢' if status == 200 else ('🟡' if status == 401 else '🔴')
    print(f'  {marker} [{ep:<28}] status={status}, rows={rows}')
    if status not in (200, 401):
        print(f'         body: {body[:120]}')
print()

# === 단계 2-C: 그 외 시도해볼만한 주요 카테고리 ===
print('=' * 80)
print('단계 2-C: 다른 카테고리 endpoint 탐색 (참고용)')
print('=' * 80)

other_guesses = [
    # idx = 지수
    ('idx/kospi_dd_trd', 'KOSPI 지수 (알려진 예시)'),
    ('idx/kosdaq_dd_trd', 'KOSDAQ 지수'),
    # 시간별
    ('sto/stk_isu_inf', 'KOSPI 종목정보'),
    ('sto/ksq_isu_inf', 'KOSDAQ 종목정보'),
    # 투자자 (추정)
    ('sto/stk_invt_trd', 'KOSPI 투자자별 매매 (추정)'),
]

for ep, label in other_guesses:
    status, body, rows = call_endpoint(ep, {'basDd': test_date}, label)
    marker = '🟢' if status == 200 else ('🟡' if status == 401 else '🔴')
    print(f'  {marker} [{ep:<28}] status={status}, rows={rows}  — {label}')
print()

print('판정:')
print('  🟢 200 = 이미 서비스 신청·사용 가능')
print('  🟡 401 = endpoint 존재, 추가 서비스 신청 필요')
print('  🔴 그 외 = endpoint 없음/ URL 오류')
