"""_v_18_nxt_utils_test.py — 접미어 유틸·상수 단위 테스트 (OCX 불필요)"""
import sys
sys.path.insert(0, r'D:\StockAnalyst')

from kiwoom_api_nxt import (
    to_nxt_code, to_all_code, extract_raw_code, get_exchange,
    NXT_SESSION_STATE, EXCH_KRX, EXCH_NXT, EXCH_ALL,
)

# 1. 접미어 유틸
assert to_nxt_code('039490') == '039490_NX'
assert to_nxt_code('005930') == '005930_NX'
assert to_nxt_code('005930_NX') == '005930_NX'  # 멱등성 (이미 NXT)
assert to_nxt_code('005930_AL') == '005930_NX'  # AL → NX 교체

assert to_all_code('039490') == '039490_AL'
assert to_all_code('005930_NX') == '005930_AL'

assert extract_raw_code('005930') == '005930'
assert extract_raw_code('005930_NX') == '005930'
assert extract_raw_code('005930_AL') == '005930'
assert extract_raw_code('') == ''

assert get_exchange('005930') == 'KRX'
assert get_exchange('005930_NX') == 'NXT'
assert get_exchange('005930_AL') == 'ALL'
assert get_exchange('') == 'KRX'

# 2. 상수
assert EXCH_KRX == '1'
assert EXCH_NXT == '2'
assert EXCH_ALL == '3'

# 3. FID 215 상태
assert NXT_SESSION_STATE['P'] == 'NXT_PRE_START'
assert NXT_SESSION_STATE['V'] == 'NXT_AFTER_END'
assert len(NXT_SESSION_STATE) == 7  # P,Q,R,S,T,U,V

# 4. NxtSessionListener (on_real 콜백 동작)
from kiwoom_api_nxt import NxtSessionListener

transitions = []
def on_t(state, code, raw):
    transitions.append((state, code, raw))

listener = NxtSessionListener(on_transition=on_t)

# FID 215 값 변화 시뮬레이션
listener.on_real('005930_NX', 'some_real_type', {215: 'P'})
listener.on_real('005930_NX', 'x', {215: 'P'})  # 중복 - 무시되어야
listener.on_real('005930_NX', 'x', {215: 'R'})  # 전환
listener.on_real('005930_NX', 'x', {'215': 'U'})  # 문자열 키도 OK
listener.on_real('005930_NX', 'x', {10: 72500})  # FID 215 없음 - 무시

assert len(transitions) == 3, f'예상 3회, 실제 {len(transitions)}회: {transitions}'
assert transitions[0] == ('NXT_PRE_START', '005930_NX', 'P')
assert transitions[1] == ('NXT_MAIN_START', '005930_NX', 'R')
assert transitions[2] == ('NXT_AFTER_START', '005930_NX', 'U')

print('모든 유틸 단위 테스트 통과.')
print(f'  NXT_SESSION_STATE: {len(NXT_SESSION_STATE)}개 상태')
print(f'  접미어 변환 멱등성 OK')
print(f'  NxtSessionListener 중복 필터 OK')
