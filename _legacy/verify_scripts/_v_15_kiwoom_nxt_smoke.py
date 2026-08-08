"""_v_15_kiwoom_nxt_smoke.py — NxtApi 스모크 테스트 (32bit Python 전용)

목적:
  1. 기존 KiwoomAPI 로그인 정상 동작
  2. NxtApi 가 로그인된 KiwoomAPI 를 받아 초기화 가능
  3. 삼성전자 NXT 1분봉 (005930_NX) 실제 조회 성공
  4. 반환 구조가 기존 KiwoomAPI.get_minute_data 와 호환
  5. KRX 분봉 vs NXT 분봉 비교 출력

실행 방법 (32bit Python 필수):
  D:\\StockAnalyst> C:\\Users\\integ\\AppData\\Local\\Programs\\Python\\Python310-32\\python.exe _v_15_kiwoom_nxt_smoke.py

주의:
  - 이 스크립트는 Seoner 계정 로그인을 요구함
  - 운영 중인 auto_trader 가 있으면 먼저 종료 후 실행 권장 (OCX 중복 로드 회피)
  - 실전 계정 로그인 시 조회만 하므로 주문 영향 없음
"""
import sys
import os
import time

# 32bit 체크 (원칙: 실측 우선)
import platform
arch = platform.architecture()[0]
if arch != '32bit':
    print(f'[ERROR] 현재 Python arch = {arch}. 32bit 필수.')
    print('32bit 경로: C:\\Users\\integ\\AppData\\Local\\Programs\\Python\\Python310-32\\python.exe')
    sys.exit(1)

sys.path.insert(0, r'D:\StockAnalyst')

from PyQt5.QtWidgets import QApplication

# Qt 애플리케이션이 있어야 QAxWidget 가능
app = QApplication.instance() or QApplication(sys.argv)

from kiwoom_api import KiwoomAPI
from kiwoom_api_nxt import NxtApi, to_nxt_code, get_exchange

print('=' * 70)
print('Phase 1b 스모크 테스트: NxtApi 실제 조회 검증')
print('=' * 70)
print()

print('[1/5] KiwoomAPI 인스턴스 생성 + 로그인 시도...')
kw = KiwoomAPI()
ret = kw.login()
print(f'  login 반환: {ret}')
if not ret:
    print('[FAIL] 로그인 실패. KOA 영웅문 점검 시간 또는 모의투자 설정 확인.')
    sys.exit(2)
print('[OK] 로그인 성공')
print()

print('[2/5] NxtApi 초기화...')
nxt = NxtApi(kw)
print(f'  nxt.kw == kw? {nxt.kw is kw}')
print('[OK] NxtApi 초기화 성공')
print()

print('[3/5] 종목코드 변환 검증...')
test_code = '005930'
nxt_code = to_nxt_code(test_code)
print(f'  원본: {test_code} -> NXT: {nxt_code} (exchange: {get_exchange(nxt_code)})')
print()

print('[4/5] KRX 1분봉 조회 (대조군)...')
try:
    krx_bars = kw.get_minute_data(test_code, tick_range=1, count=5)
    if krx_bars:
        print(f'  KRX count: {len(krx_bars["close"])}')
        print(f'  KRX 최근 5봉 close: {krx_bars["close"][-5:]}')
        print(f'  KRX 최근 5봉 time:  {krx_bars["time"][-5:]}')
    else:
        print('  KRX 분봉 None — 장 휴장 또는 데이터 없음')
except Exception as e:
    print(f'  [ERROR] KRX 분봉 조회 예외: {e}')
print()

print('[5/5] NXT 1분봉 조회 (실측 대상)...')
try:
    nxt_bars = nxt.get_minute_bars(test_code, tick_range=1, count=5)
    if nxt_bars:
        print(f'  NXT count: {len(nxt_bars["close"])}')
        print(f'  NXT 최근 5봉 close: {nxt_bars["close"][-5:]}')
        print(f'  NXT 최근 5봉 time:  {nxt_bars["time"][-5:]}')
        print('[SUCCESS] NXT 분봉 조회 정상 동작 확인')
    else:
        print('  [WARN] NXT 분봉 None — 조건 점검 필요:')
        print('    - NXT 장 시간 외 (08:00~20:00 외)')
        print('    - 해당 종목이 NXT 거래대상 아님')
        print('    - 종목코드 "_NX" 접미어 미지원 (스펙 재확인 필요)')
except Exception as e:
    print(f'  [ERROR] NXT 분봉 조회 예외: {type(e).__name__}: {e}')
print()

print('=' * 70)
print('스모크 테스트 완료. 정상이면 위 "[SUCCESS]" 문구 확인됨.')
print('=' * 70)
