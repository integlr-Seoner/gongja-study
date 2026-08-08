# 코드 작성 전 필수 체크리스트

> **Claude AI는 코드 작성 전 이 문서를 반드시 읽고 체크리스트를 확인해야 합니다.**
> 마지막 갱신: 2026-04-02

---

## ⛔ 코드 작성 전 필수 확인

### 0. 결함 대조 (2026-02-08 추가 — 진단하고 수정에서 빠뜨리는 습관 방지)

```
❌ 나쁜 예: 진단서에 6개 결함 써놓고 → 수정할 때 진단서 안 보고 → 2개 누락
❌ 나쁜 예: "최소 범위 수정"이라며 이미 결함으로 확인된 코드를 새 함수에 복사
✅ 좋은 예: 수정 전에 진단서/결함 목록 열어서 이 수정과 관련된 결함 전부 확인
```

- [ ] **이 작업에 관련된 진단서/결함 목록이 있는가?** → 있으면 열어서 대조
- [ ] **복사하려는 기존 코드가 이미 결함으로 확인된 것 아닌가?** → 결함 코드 복사 금지
- [ ] **"최소 범위 수정"을 결함 방치의 핑계로 쓰고 있지 않은가?**
- [ ] **수정 완료 후, 진단서의 관련 결함이 전부 해소되었는지 재확인**

### 1. 기존 코드 패턴 확인

```
❌ 나쁜 예: "이렇게 하면 되겠지" → 추측으로 코드 작성
✅ 좋은 예: 유사 기능이 어떻게 구현되어 있는지 먼저 확인
```

- [ ] 수정 대상 클래스/함수의 실제 정의 확인했는가?
- [ ] 필드 타입, 반환 타입 확인했는가?
- [ ] 연관 모듈의 사용 방식 확인했는가?
- [ ] 같은 종류의 다른 기능이 어떻게 구현되어 있는지 확인했는가?

---

## 🔴 DB 관련 수정 시 (스캔 결과)

### 저장 쿼리 작성 시

- [ ] `created_at` 컬럼 포함하는가?
- [ ] `created_at`에 `datetime.now()` 값 저장하는가?
- [ ] 자체 _v2 테이블과 strategy_results 둘 다 저장하는가?
- [ ] 저장 경로가 로드 경로와 일치하는가?

### 로드 쿼리 작성 시

```python
# ✅ 올바름
ORDER BY created_at DESC

# ❌ 잘못됨 - 스캔 테이블에 date DESC 사용 금지!
ORDER BY date DESC
```

- [ ] `ORDER BY created_at DESC` 사용하는가?
- [ ] `ORDER BY date DESC` 사용하지 않았는가? (스캔 테이블)
- [ ] **`LIMIT` 쓰면 `ORDER BY` 반드시 동반하는가?** (순서 없는 LIMIT은 무의미)

### 루프 내 API/DB 대량 처리 시 (2026-02-08 추가)

```python
# ❌ 나쁜 예: 수백 건 연속 API 호출, 보호 없음
for code in codes:
    data = api.get_ohlcv(code)  # Rate Limit 위험

# ✅ 좋은 예: 호출 간격 + 배치 크기 제한
for i, code in enumerate(codes):
    data = api.get_ohlcv(code)
    if (i + 1) % 50 == 0:
        time.sleep(1)  # Rate Limit 방지
```

- [ ] 루프 내 외부 API 호출이 있는가? → **time.sleep() 또는 배치 간격 필수**
- [ ] 대량 DB UPDATE가 있는가? → **중간 커밋 + BATCH_SIZE 제한**
- [ ] 에러 시 부분 처리 상태가 되는가? → **멱등성 확인 (재실행해도 안전한가)**

### DB 커넥션 안전 패턴 (2026-04-02 추가 — 388건 누수 발견)

```
❌ 나쁜 예: 예외 시 conn.close() 도달 못함 (프로젝트 전체 388건 발견)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT ...")  # ← 여기서 예외 발생하면
conn.close()                  # ← 이 줄 실행 안 됨 → 커넥션 누수

✅ 좋은 예: try/finally로 반드시 close
conn = sqlite3.connect(db_path)
try:
    cursor = conn.cursor()
    cursor.execute("SELECT ...")
    conn.commit()
finally:
    conn.close()
```

- [ ] **sqlite3.connect() 사용 시 반드시 try/finally: conn.close() 패턴 적용했는가?**
- [ ] **기존 코드를 복사할 때 해당 코드가 이미 결함(finally 누락)이 아닌지 확인했는가?**

### 스캔 테이블 목록 (date DESC 금지)

```
rs_targets_v2, bb_squeeze_v2, abcd_targets_v2, farley_signals_v2,
smc_structure_v2, scanned_targets_v2, ultimate_targets_v2,
modern_targets, mlpredict_v2, vsa_v2, sentiment_v2, orderflow_v2,
mtf_results, shakeout_targets, filtered_targets, plugin_results,
strategy_results, strategy_recommendations, unified_rankings
```

### 예외 (date DESC 사용 가능)

```
trade_history, trade_log, simulation_performance
(매매 이력은 날짜 기준 조회가 맞음)
```

---

## 🔴 새 전략/기능 추가 시

### 저장 함수 체크리스트

- [ ] 자체 _v2 테이블 저장 함수 구현했는가?
- [ ] 테이블 CREATE 문에 created_at TEXT 포함하는가?
- [ ] INSERT 시 created_at 값 설정하는가?
- [ ] strategy_results에도 저장하는가? (fallback용)

### 로드 핸들러 체크리스트

- [ ] 저장 경로와 동일한 테이블에서 로드하는가?
- [ ] ORDER BY created_at DESC 사용하는가?
- [ ] 같은 종류의 다른 전략 로드 코드와 패턴이 일치하는가?

---

## 🔴 API 함수 수정 시

### PyQt 시그니처 체크리스트

- [ ] JS에서 호출하는 인자 개수와 @pyqtSlot 데코레이터 일치하는가?
- [ ] 여러 시그니처 지원 시 구체적인 것이 먼저인가?

```python
# ✅ 올바른 순서 (구체적인 것 먼저)
@pyqtSlot(str, str, result=str)
@pyqtSlot(result=str)
def myFunction(self, arg1: str = '', arg2: str = '') -> str:

# ❌ 잘못된 순서
@pyqtSlot(result=str)
@pyqtSlot(str, str, result=str)
def myFunction(self, arg1: str = '', arg2: str = '') -> str:
```

---

## 🔴 UI/DOM 관련 수정 시

- [ ] `document.getElementById()` 반환값 null 체크하는가?
- [ ] setInterval에서 DOM 요소 접근 전 존재 여부 재확인하는가?
- [ ] try-catch로 에러 처리하는가?

```javascript
// ✅ 올바름
const el = document.getElementById('my-element');
if (el) {
    el.textContent = 'value';
}

// ❌ 잘못됨
document.getElementById('my-element').textContent = 'value';
```

---

## 🔴 HTML 테이블/구조 수정 시 (UI 컬럼 추가/삭제)

### 수정 전 필수 확인

```bash
# 기존 테이블 헤더 구조 확인 (필수!)
# 어떤 컬럼이 있는지 정확히 파악
```

- [ ] 기존 테이블 헤더(`<th>`) 목록을 **전부** 확인했는가?
- [ ] 기존 테이블 행(`<td>`) 목록을 **전부** 확인했는가?
- [ ] 추가할 컬럼 위치를 **명시적으로** 결정했는가? (예: "신호 뒤, 전략수 앞")

### 수정 방식

```javascript
// ❌ 잘못됨 - 전체 재작성 (기존 컬럼 누락 위험)
html += '<th>A</th><th>B</th><th>C</th><th>새컬럼</th><th>D</th>';

// ✅ 올바름 - 기존 구조 유지하며 삽입 위치만 변경
// 기존: A, B, C, D
// 변경: A, B, C, 새컬럼, D  (C와 D 사이에 삽입)
```

### 수정 후 필수 검증

- [ ] `git diff`에서 **삭제된 컬럼**이 없는지 확인했는가?
- [ ] 헤더(`<th>`) 개수와 행(`<td>`) 개수가 일치하는가?
- [ ] 기존에 있던 모든 컬럼이 여전히 존재하는가?

---

## ⛔ 커밋 전 필수 실행

```bash
python D:\StockAnalyst\pre_commit_check.py
```

이 스크립트가 경고를 출력하면 반드시 수정 후 커밋!

---

## 🔴 과거 실수 사례 (반복 금지!)

### 2026-02-07: 진단서 작성 후 수정에서 누락 (3건)
- 6개 구조적 결함을 진단서에 정리해놓고 수정 시 진단서를 안 봄
- 결함 #5(closes[5] 인덱스 기반)를 새 함수 `_fetch_and_calc()`에 그대로 복사
- LIMIT 200 넣으면서 ORDER BY 누락 → 어떤 200건인지 무작위
- backfill 26일치 수백 건 API 호출에 Rate Limit 보호 없음
- 원인: **진단서 대조 단계 자체가 프로세스에 없었음** + 기본 습관 부재
- 교차 검증(Perplexity/Gemini)으로 발견 → 자체 검출 실패

### 2026-01-23: UI 테이블 컬럼 삭제 실수
- 투자스타일 테이블에 PER/PBR/ROE/F등급 컬럼 추가 작업
- 기존 헤더 구조 확인 없이 전체 재작성
- 결과: **기존 '전략수' 컬럼 삭제됨**
- 원인: SESSION_START.md "기존 코드 패턴 확인 필수" 원칙 무시

### 2026-01-20: DB 저장/로드 경로 불일치
- SMC 스캔 → closing_bet.db에 저장
- DB 로드 → trading_system.db에서 조회
- 결과: 10일 전 데이터 표시

### 2026-01-20: ORDER BY date DESC 사용
- 장 시작 전 스캔 → date=전일로 저장
- ORDER BY date DESC → 최신 스캔 아닌 다른 날짜 데이터 반환
- 결과: 각 전략마다 다른 날짜 데이터 표시

### 2026-01-19: IntegratedAnalysis 필드 타입 오류
- 클래스 구조 확인 없이 추측으로 코드 작성
- 결과: 전략분석 전체 실패

### 공통 원인
1. SESSION_START.md 안 읽음
2. 기존 코드 패턴 확인 안 함
3. 추측으로 코드 작성
4. 변경 후 검증 안 함
5. **진단서/결함 목록 작성 후 수정 시 대조 안 함** (2026-02-08 추가)
6. **"최소 범위 수정"을 결함 방치의 핑계로 사용** (2026-02-08 추가)
7. **매수/매도 조건의 정합성 교차 검증 안 함** (2026-04-02 추가)
8. **결함 코드(finally 누락)를 새 기능에 반복 복사** (2026-04-02 추가)

### 2026-04-02: ABCD B점 매수/매도 정합성 미검증
- 매도 조건: B점 돌파 → 1차 드리블 매도
- 매수 조건: B점은 가산점(+20)일 뿐, 차단 아님
- 결과: 삼성SDI B점 위에서 매수 → 29초 후 즉시 매도 (+2,289원)
- 근본 원인: 같은 날(1/12) 오전 매도, 오후 매수를 나눠서 구현하면서 교차 검증 안 함
- 80일간 잠복 후 실전 매매에서 발현

### 2026-04-02: DB 커넥션 누수 388건 (프로젝트 전체)
- sqlite3.connect() 후 finally: conn.close() 패턴 미적용
- 최초 도입: 2026-01-05 (자동매매 최초 구현) → 이후 모든 기능에 동일 패턴 확산
- pre_commit_check.py가 새 코드만 검사하여 기존 코드 미검출
- 결함 진단서: docs/DEFECT_AUDIT_2026-04-02.md (482건)

---

## 🎯 점수/가중치 관련 원칙

### 임의 점수 할당 금지

```
❌ 나쁜 예: "WhaleCVD면 +10점, Sentiment면 +5점" (근거 없음)
✅ 좋은 예: strategy_performance 테이블에서 실제 수익률/승률 확인 후 결정
```

### 가중치 적용 기준

- [ ] **충분한 데이터**: 최소 100건 이상의 성과 데이터 축적
- [ ] **명확한 근거**: 평균 대비 유의미한 차이 (예: 3일 수익률 2배 이상)
- [ ] **검증 가능**: 백테스트 또는 실거래 성과로 검증

### 현재 성과 데이터 요약 (2026-01-31 기준)

| 전략 | 건수 | 3일 수익률 | 전체 평균 대비 |
|------|------|------------|----------------|
| SupplyDemand | 338 | +5.51% | **3배** (가산 검토 가능) |
| Sentiment | 374 | +1.95% | 비슷 (가산 불필요) |
| RS | 548 | +0.06% | 이하 (가산 불필요) |
| WhaleCVD | - | 데이터 없음 | 축적 후 재평가 |

> **원칙**: 데이터가 쌓이고 근거가 명확해지면 그때 점수/가중치를 적용한다.

### 시장 상황별 가중치 (2026-01-31 결정)

```
현재 상태:
  - 상승장 데이터: 있음 (2025-12~2026-01)
  - 하락장 데이터: 없음
  - 횡보장 데이터: 없음

결정: 실제 운용 데이터 축적 후 적용 (방안 B)
  - 임의 가중치 적용하지 않음
  - 3~6개월 데이터 축적 후 백테스트 재실행
  - 재검토 시점: 2026-07-01

자동화:
  - market_condition_collector.py: 매일 시장 상황 기록
  - strategy_backtester.py: 분기별 재분석

백테스트 재실행 조건:
  - 하락장 데이터 30일 이상 축적
  - 횡보장 데이터 30일 이상 축적
```

---

## 🔵 Phase 단위 작업 지침 준수 보고 (2026-04-09 추가)

> Claude는 매 Phase 완료 후 아래 체크리스트를 반드시 보고한다.

```
Phase N 완료 보고:
  ✅/❌ SESSION_START.md 읽기
  ✅/❌ BEFORE_CODING.md 읽기
  ✅/❌ 기존 코드 패턴 확인 후 작성
  ✅/❌ 추측 코딩 없음
  ✅/❌ created_at 포함
  ✅/❌ ORDER BY created_at DESC (해당 시)
  ✅/❌ closing() 패턴
  ✅/❌ sleep() (루프 API 호출 시)
  ✅/❌ pre_commit_check.py 통과
  ✅/❌ smoke_test 24/24 통과
```

---

## 🟡 재료 매매 시스템 (2026-04-09 추가)

### material_keywords.py 수정 시

- [ ] `ast.parse()` 구문 검사 통과했는가?
- [ ] 추가 키워드가 기존 카테고리와 충돌/중복 없는가? (우선순위 순서 확인)
- [ ] 새 카테고리 추가 시 `web/app.js` 배지 색상도 추가했는가?

```python
# 카테고리 22개: bonus_issue/rights_issue/convertible_bond/exchangeable_bond/
# bond_warrant/supply_contract/world_first/game_theme/movie_drama/
# bigcorp_invest/bigcorp_entry/bigcorp_collab/mgmt_dispute/
# ma_acquisition/ipo_listing/trial_schedule/gov_policy/political_theme/
# epidemic/material_exhaustion/earnings_miss/biotech
```

### 재료 소멸 기준값 (변경 시 근거 필수)

```
A등급: 하락 -5%+, TV 2배+, 몸통 3%+   (Q&A Q25 기반)
B등급: 하락 -3%+, TV 1.5배+, 몸통 2%+
→ 단순 주가 하락만으로 재료 소멸 판단 금지
```

### material_momentum_score.py 사용 시

```
뉴스 API(네이버) 의존 → 뉴스 0건이면 news_freq=0 → D등급 많음
kb_open 값 넣으면 기준봉 시가 유지 10점 추가
→ 기준봉 발생 후 3~5일 모멘텀 지속 확인 용도로만 사용
```
