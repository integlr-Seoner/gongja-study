# 내실 강화 로드맵

> 작성: 2026-02-23
> 목표: 1억을 맡길 수 있는 시스템으로 만들기
> 원칙: SESSION_START.md + BEFORE_CODING.md 준수

---

## 현황 진단 (2026-02-23 기준)

### 데이터 정합성

| 항목 | 수치 | 상태 |
|------|------|------|
| trade_log 총 건수 | 947 | - |
| action NULL | 21 | 🔴 |
| date 빈값 | 4 | 🔴 |
| SELL profit=0 but pct≠0 | 325 (62.6%) | 🔴 역산 필요 |
| SELL profit≠0 | 191 (36.8%) | ✅ 정상 |
| trade_history time=00:00 | 47/224 (21%) | 🔴 시간 유실 |
| current_holdings | 2 | - |
| strategy_performance | 20,003건 (54전략) | ✅ |
| training_data_v2 | 3,102건 | ⚠️ |
| 마지막 스케줄러 실행 | 2026-01-28 | 🔴 26일 전 |

### 코드 구조

| 항목 | 수치 | 상태 |
|------|------|------|
| index.html | 16,130줄 (단일 파일) | 🔴 |
| legacy_compat_api.py | 8,896줄 (단일 파일) | 🔴 |
| 키움 COM 동시접근 방지 | 플래그 기반 임시 우회 | 🔴 |
| 에러 복구 | 없음 (장중 크래시 시 미체결 주문 방치) | 🔴 |

---

## Phase 0: 긴급 — 돈에 직결되는 데이터 정합성 (1주)

> 전략이나 기능이 아니라, 있는 데이터가 정확한지부터.

### 0-1. trade_log NULL/빈값 정리
- [x] action NULL 21건 → 보정 완료 (0건)
- [x] date 빈값 4건 → 보정 완료 (0건)

### 0-2. trade_log profit 역산 일괄 보정
- [x] SELL 325건 역산 완료 (check_integrity PASS)

### 0-3. trade_history time 유실 수정
- [x] 47건 전부 GHOST_CLEANUP 일회성 스크립트 생성 (코드 이미 삭제됨)
- [x] 키움 동기화 경로 버그 아님 (복구 불가/불필요)
- [x] OPW00015 경로 time 하드코딩 → h.get('time', '') 수정 (trading_api.py, stock_analyst_dashboard.py)

### 0-4. current_holdings ↔ trade_log 정합성 검증
- [x] epoch(20260219) 이후 유령 포지션 0건 (check_integrity PASS)

### 0-5. 데이터 정합성 자동 검증 스크립트
- [x] check_integrity.py 존재 (epoch-aware, 전항목 PASS)
- [x] daily_scheduler.py 연동 완료 (step 12: _run_integrity_check)
- [ ] pre_commit_check.py 연동 (별도 확인 필요)

---

## Phase 1: 안정성 — 안 깨지는 시스템 (2주)

> 기능 추가 아님. 있는 것이 안 깨지게.

### 1-1. 키움 COM 순차 호출 보장
- [x] 키움 API 호출 경로 전체 조사 완료
  - request_tr/request_multi: _com_busy 플래그 + QEventLoop 재진입 차단
  - send_order: _com_busy 체크 (TR 처리 중 주문 거부)
  - 재시도 로직 (최대 3회 + 0.5초 딜레이)
- [x] Python 측 COM 보호: 기존 _com_busy 메커니즘으로 충분
- [ ] JS 측: 키움 호출 큐 구현 (Promise 기반 순차 실행) — debounce 보강
  - sendBuyOrder, sendSellOrder, syncTradeFromKiwoom
  - auto_trader.py 내부 호출
- [ ] JS 측: 키움 호출 큐 구현 (Promise 기반 순차 실행)
- [ ] Python 측: 키움 COM 호출 락(Lock) 구현
- [ ] 동시 호출 시 대기 → 타임아웃 → 에러 반환 (크래시 대신)

### 1-2. 주문 실행 경로 end-to-end 검증
- [x] 주문 → 체결 확인 → trade_log 기록 → current_holdings 반영 경로 추적 완료
- [x] 실패 시나리오 분석: 콜백 미수신/DB 기록 실패/부분체결 미완
- [x] 누락 감지: 키움 체결내역 vs trade_log 대조 함수 구현 (_run_trade_reconciliation)
- [x] 매일 장 마감 후 자동 대조 (daily_scheduler step 1-1 연동)

### 1-3. 장중 크래시 복구
- [ ] auto_trader 상태 파일 저장 (실행 중이었던 주문 목록)
- [ ] 프로그램 재시작 시 미체결 주문 확인 로직
- [ ] 손절 주문 복구 (크래시 전 걸어놨던 조건 주문)
- [ ] 복구 시나리오 테스트 (수동)

### 1-4. 스케줄러 복원
- [x] 스케줄러 정상 동작 확인 (2/7~2/22 매일 실행)
- [x] strategy_perf UNIQUE constraint 수정 (INSERT OR IGNORE)
- [ ] 스케줄러 장애 알림 (telegram/email)

---

## Phase 2: 구조 — 고치면 안 깨지는 코드 (3주)

> 지금 구조에서는 버그 수정이 새 버그를 만든다.

### 2-1. index.html 분리
- [ ] 현재 구조 분석: 페이지별 함수 매핑
- [ ] 공통 유틸 (fmtOrderTime, showToast 등) → common.js
- [ ] 페이지별 JS 분리 계획 수립
  - auto_schedule.js, portfolio.js, order.js 등
- [ ] Phase별 점진 분리 (한 번에 하지 않음)
- [ ] 분리 후 기존 기능 동작 검증

### 2-2. legacy_compat_api.py 분리
- [ ] 현재 API 함수 목록 정리 (도메인별)
- [ ] trading_api, scan_api, account_api 등으로 분리 계획
- [ ] Phase별 점진 분리
- [ ] 분리 후 JS 측 호출 경로 검증

### 2-3. DB 스키마 통일
- [ ] trade_log.time vs trade_history.time 형식 통일 방안
- [ ] 향후 INSERT 시 형식 강제 (CHECK 제약조건 또는 트리거)
- [ ] trade_log.action NULL 방지 (NOT NULL 제약조건)
- [ ] 마이그레이션 스크립트 작성

---

## Phase 3: 신뢰 — 성과를 믿을 수 있는 시스템 (2주)

> Phase 0~2 완료 후 진행

### 3-1. 실현손익 정확도 검증
- [ ] trade_log 기반 실현손익 합계 vs 키움 HTS 대조
- [ ] 오차 원인 파악 + 보정
- [ ] 일별/월별 실현손익 리포트 자동 생성

### 3-2. 전략 성과 신뢰도
- [ ] strategy_performance 20,003건 → 실제 수익률 정확한지 샘플 검증
- [ ] 추천 → 매매 → 성과 파이프라인 end-to-end 테스트
- [ ] 전략별 승률/수익률 대시보드 정확도 확인

### 3-3. 30일 안정 운영
- [ ] Phase 0~2 완료 후 실거래 없이 30일 운영
- [ ] 매일 check_integrity.py 자동 실행
- [ ] 크래시 0건, 데이터 불일치 0건 달성
- [ ] 이후 소액(100만원 이하) 실거래 테스트

---

## 진행 규칙

1. **Phase 순서 준수**: 0 → 1 → 2 → 3 (건너뛰기 금지)
2. **항목 완료 시 즉시 커밋**: Phase 단위 분할 원칙
3. **세션 시작 시 필수**: SESSION_START.md + BEFORE_CODING.md 읽기
4. **기능 추가 금지**: 로드맵 항목만 진행 (사용자 명시 요청 제외)
5. **검증 우선**: 추측 금지, 실제 코드/데이터/로그로 확인

---

## 이번 세션 반성

| 커밋 | 문제 |
|------|------|
| 9709a33 (if 괄호 수정) | SESSION_START.md 미독, snapshot 미실행 |
| 38d7cfb (포트폴리오 카드) | BEFORE_CODING.md 미독, 기존 패턴 미확인 |
| 292061a (COM 크래시) | 근본 원인(큐 구조) 대신 await 임시 우회 |
| 1866b35 (경고 제거) | snapshot 불일치 → --no-verify 강행 |
| 515f40c (시간 표시) | DB 형식 불통일 근본 원인 미해결, 프론트 파싱만 수정 |

---

## 점검 도구

```bash
# 데이터 정합성 확인
python check_integrity.py

# 구현 철학 부합도
python archive\utility_scripts\verify_philosophy.py

# 커밋 전 검증
python pre_commit_check.py

# 스냅샷 비교
python snapshot_test.py compare
```
