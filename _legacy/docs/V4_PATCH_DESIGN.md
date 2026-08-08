# V4 카운트 기반 점수 시스템 — closing_bet_unified.py 패치 설계서

**작성일**: 2026-04-22  
**대상**: `D:\StockAnalyst\closing_bet_unified.py` (70,896 chars)  
**근거 문서**: `PHASE_1A_DATA_SOURCES.md` §11~18 (전체 검증 트랙)  
**원칙 준수**: ①Think Before Coding · ②Simplicity First · ③Surgical Changes · ④Goal-Driven

---

## 1. 배경 및 목표

### 1.1 V4 정의 (검증 완료)
정배열+장대양봉 / 60일 신고가 / 거래대금 3배↑ / 종가 95%↑ — 4조건 각 1점 → 0~4 정수 점수.

### 1.2 검증 결과 요약
| 측정 | 결과 |
|------|------|
| `_v_26` 단조 증가성 | 역전 0회 (현재 체계 2회) |
| `_v_26` score==4 평균 수익 | mean +3.504%, realized +3.044%, conservative +2.744% |
| `_v_26` score==4 승률 | 63.1% |
| `_v_27` Mode A CAGR | +43.72% (시드 ±0.00) |
| `_v_27` Mode A MDD | -1.6% |
| `_v_27` Mode A Sharpe | 8.90 |
| `_v_27` 시기 분할 | STABLE (P1/P2/P3 cv=0.14) |
| `_v_27` 연도별 | 13/13 연도 양수 |

### 1.3 패치 목표
- 신규 메서드 `predict_v4()` 추가 (기존 `predict()` 무수정)
- 신규 등급 `STRONG_BUY` / `BUY` / `WATCH`
- 외부 호환성 100% 유지 (기존 호출처 0건 변경)
- 운영 채택 후 `predict()` 호출처를 점진적으로 `predict_v4()` 로 마이그레이션

---

## 2. 영향 범위 실측

### 2.1 `predict()` 호출처 (외부 사용)
- `D:\StockAnalyst\api\legacy_scan_ext_api.py:947` — `predictor.predict(code, df, ...)` → `pred.get('total_score', 0) >= 40`
- `D:\StockAnalyst\api\legacy_scan_ext_api.py:1051` — 동일 패턴
- **사용 키 단 1개**: `total_score` (정수, 0~100 가정)

### 2.2 내부 헬퍼 (외부 호출 0)
- `_score_chart_pattern` — 호출처 0 (closing_bet_unified.py 내부 전용)
- `_score_trading_value` — 호출처 0
- `_score_close_position` — 호출처 0
- `_determine_grade` — 호출처 0
- `_get_recommendation` — 호출처 0

### 2.3 별도 시스템 (영향 없음)
- `closing_bet_filter.cb_score` (A/B/C/D 4등급) — 별개 트랙
- `screener_v67.cb_score` (cb_grade 컬럼) — 별개 트랙
- `closing_bet_unified.ClosingBetMonitor._calculate_score` (장중 모니터링용) — 별개 트랙

→ **패치 영향 범위 = `closing_bet_unified.py` 내부 + 외부 2곳 (legacy_scan_ext_api.py)**

---

## 3. 패치 설계 (3단계)

### 3.1 Stage 1 — 신규 메서드 추가 (CHANGE_PLAN_1)
- 파일: `closing_bet_unified.py`
- 위치: `predict()` 메서드 직후 (현재 file offset 약 55,500 부근)
- 변경량: +90줄 신규, 0줄 수정
- 회귀 위험: **0** (기존 코드 무수정)

```python
def predict_v4(self, code: str, ohlcv: pd.DataFrame) -> dict:
    """V4 카운트 기반 점수 (0~4 정수)
    
    검증 결과 (PHASE_1A_DATA_SOURCES.md §17~18):
        score==4: realized +3.044%, 승률 63.1%, MDD -1.6%, Sharpe 8.90, CAGR +43.72%
        score==3: realized +0.370%
        score≤2:  realized < 0
    
    Returns:
        {
            'code': str,
            'v4_score': int (0~4),
            'v4_grade': str ('STRONG_BUY'/'BUY'/'WATCH'),
            'v4_conditions': dict (각 조건 충족 bool),
            'expected_gap': str,
            'recommendation': str,
            # 기존 predict() 호환 키 (마이그레이션용)
            'total_score': int (v4_score * 25, 0~100 환산),
            'grade': str (HIGH/MEDIUM/LOW 환산),
            'breakdown': dict,
        }
    """
    if len(ohlcv) < 60:
        return self._empty_result_v4(code, "데이터 부족")
    
    # 4조건 평가 (검증된 정의 그대로)
    cond1 = self._is_align_and_big_candle(ohlcv)      # 정배열+장대양봉
    cond2 = self._is_60day_new_high(ohlcv)            # 60일 신고가
    cond3 = self._get_volume_value_ratio(ohlcv) >= 3.0 # 거래대금 3배↑
    cond4 = self._get_close_position(ohlcv) >= 0.95   # 종가 95%↑
    
    v4_score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    
    # 등급
    if v4_score == 4:
        grade = "STRONG_BUY"; gap = "3-5%+"; rec = "적극 매수 (4조건 모두 충족, realized +3.044%)"
        legacy_grade = "HIGH"
    elif v4_score == 3:
        grade = "BUY"; gap = "0-1%"; rec = "보조 매수 (realized +0.370%)"
        legacy_grade = "MEDIUM"
    else:
        grade = "WATCH"; gap = "불확실"; rec = "관망 (조건 부족)"
        legacy_grade = "LOW" if v4_score == 2 else "VERY_LOW"
    
    return {
        'code': code,
        'v4_score': v4_score,
        'v4_grade': grade,
        'v4_conditions': {
            'align_and_big_candle': cond1,
            'new_high_60d': cond2,
            'volume_value_3x': cond3,
            'close_position_95': cond4,
        },
        'expected_gap': gap,
        'recommendation': rec,
        # 기존 predict() 키 호환 (마이그레이션용)
        'total_score': v4_score * 25,  # 0/25/50/75/100
        'grade': legacy_grade,
        'breakdown': {'v4_chart': (int(cond1)+int(cond2))*25,
                     'v4_volume': int(cond3)*25,
                     'v4_position': int(cond4)*25,
                     'news': 0},
    }
```

### 3.2 Stage 2 — 헬퍼 메서드 추가 (CHANGE_PLAN_2)
- 위치: `predict_v4()` 직후
- 변경량: +60줄 신규, 0줄 수정
- 회귀 위험: **0**

```python
def _is_align_and_big_candle(self, ohlcv: pd.DataFrame) -> bool:
    """정배열(MA5>MA10>MA20) + 장대양봉(body/range > 0.6)"""
    c = ohlcv['Close'].values
    o = ohlcv['Open'].values
    h = ohlcv['High'].values
    l = ohlcv['Low'].values
    if len(c) < 20:
        return False
    ma5 = c[-5:].mean()
    ma10 = c[-10:].mean()
    ma20 = c[-20:].mean()
    if not (ma5 > ma10 > ma20):
        return False
    body = c[-1] - o[-1]
    rng = h[-1] - l[-1]
    return rng > 0 and body > 0 and (body / rng > 0.6)

def _is_60day_new_high(self, ohlcv: pd.DataFrame) -> bool:
    """오늘 high가 직전 60일 max 초과"""
    h = ohlcv['High'].values
    if len(h) < 61:
        return False
    return h[-1] > h[-61:-1].max()

def _get_volume_value_ratio(self, ohlcv: pd.DataFrame) -> float:
    """오늘 거래대금 / 직전 20일 평균 거래대금"""
    c = ohlcv['Close'].values
    v = ohlcv['Volume'].values
    if len(c) < 21:
        return 0.0
    today_tv = c[-1] * v[-1]
    avg20_tv = (c[-21:-1] * v[-21:-1]).mean()
    return today_tv / avg20_tv if avg20_tv > 0 else 0.0

def _get_close_position(self, ohlcv: pd.DataFrame) -> float:
    """종가의 일중 위치 (0=저가, 1=고가)"""
    h = ohlcv['High'].values[-1]
    l = ohlcv['Low'].values[-1]
    c = ohlcv['Close'].values[-1]
    rng = h - l
    return (c - l) / rng if rng > 0 else 0.0

def _empty_result_v4(self, code: str, reason: str) -> dict:
    return {
        'code': code, 'v4_score': 0, 'v4_grade': 'WATCH',
        'v4_conditions': {}, 'expected_gap': '불확실', 'recommendation': reason,
        'total_score': 0, 'grade': 'VERY_LOW', 'breakdown': {},
    }
```

### 3.3 Stage 3 — 마이그레이션 (선택, 추후)
- 운영 시스템에서 충분히 검증된 후 진행
- `legacy_scan_ext_api.py:947, 1051` 의 `predictor.predict(...)` → `predictor.predict_v4(...)` 로 변경
- 컷오프 `>= 40` 유지 시 `total_score` 환산값 (v4_score * 25) 활용
  - v4_score=2 → total_score=50 (>= 40 통과)
  - v4_score=1 → total_score=25 (미통과)
  - 결과: 사실상 v4_score >= 2 컷오프

→ **Stage 3 는 이번 패치 범위에서 제외**. Stage 1+2 만 적용 후 운영 검증 후 결정.

---

## 4. 검증 절차 (4단계)

### 4.1 Pre-commit
```bash
cd D:\StockAnalyst
D:\StockAnalyst\venv\Scripts\python.exe pre_commit_check.py
```
→ 13/13 통과 필수.

### 4.2 단위 테스트 (신규)
```bash
# _v_28_predict_v4_unit.py 작성 예정
# - score==4 케이스 1개 (예: V4 검증 데이터의 실제 종목)
# - score==3 케이스 1개
# - score==0 케이스 1개
# - empty / NaN / 데이터 부족 케이스
```

### 4.3 회귀 테스트
- 기존 `predict()` 호출 → 동일 결과 보장 (코드 무수정이므로 자동)
- 기존 `_v_23 ~ _v_27` 스크립트들 재실행 → 동일 결과 산출 보장

### 4.4 통합 검증
- `legacy_scan_ext_api.py:947, 1051` 그대로 두고 V4 신규 endpoint 추가 가능성 검토
- dashboard 표시용 `v4_score` 컬럼 추가 검토 (별도 작업)

---

## 5. 회귀 위험 평가

| 위험 카테고리 | 평가 | 근거 |
|--------------|------|------|
| 기존 `predict()` 동작 변경 | **0** | 무수정 |
| 기존 호출처 (`legacy_scan_ext_api.py` 2곳) 호환성 | **0** | predict() 그대로 |
| `closing_bet_filter` 영향 | **0** | 별개 시스템 |
| `screener_v67` 영향 | **0** | 별개 시스템 |
| `auto_trader` 영향 | **0** | 별개 시스템 |
| ML 모델 학습 데이터 영향 | **0** | DB 스키마 무변경 |
| 신규 메서드 자체 버그 | **저** | 단위 테스트 필수 |

**종합 회귀 위험: 매우 낮음** (Stage 1+2 만 적용시)

---

## 6. DB 스키마 변경 (없음)

V4 점수를 DB에 저장하려면 별도 작업 필요:
- `scanned_targets_v2` 테이블에 `v4_score INTEGER` 컬럼 추가
- 또는 별도 테이블 `v4_scan_results` 신설
- → **이번 패치 범위 제외**, 메모리 계산만 (호출 시점 즉시 반환)

---

## 7. 운영 채택 시뮬레이션

### 7.1 일평균 시그널 (`_v_27` 실측)
- score==4: 약 3.5건/일 (10,467 / 2,956일)
- score==3: 약 12건/일 (35,364 / 2,956일)

### 7.2 자본 운용 (Mode A 권고)
- 총 자본 1억 → 운용 30% (3,000만원) → 종목당 5% (150만원) → 동시 max 30 포지션
- score==4 전종목 매수 시 평균 일 3.5종목 × 150만원 = 525만원 운용 (cash buffer 충분)

### 7.3 리스크 관리
- Circuit Breaker: -3%/1d, -5%/7d, -10%/30d (auto_trader 통합 필요)
- 일별 손실 -3% 시 다음 1영업일 진입 중단

---

## 8. 적용 후 권고 작업

| 우선도 | 작업 |
|-------|------|
| ⭐⭐⭐ | `_v_28_predict_v4_unit.py` 단위 테스트 작성 |
| ⭐⭐⭐ | Pre-commit + 회귀 검증 |
| ⭐⭐ | Stage 3 마이그레이션 검토 (운영 1주 검증 후) |
| ⭐⭐ | dashboard `v4_score` 표시 추가 (별도 작업) |
| ⭐ | DB 스키마 확장 (`v4_score` 컬럼) |
| ⭐ | auto_trader 의 V4 시그널 진입 로직 통합 |

---

## 9. 미해결 질문 (Seoner 결정 필요)

1. **Stage 1+2 패치 즉시 적용 vs 추가 검증 후 적용?**  
   - 즉시: 코드만 추가, 호출 0이라 실제 사용 안 됨 → 안전
   - 추가 검증: 단위 테스트 먼저 작성 후 적용

2. **V4 score==4 종목의 실전 사례 검증 필요?**  
   - 최근 1개월 score==4 종목들을 추출해 실제 갭업 확률 확인
   - 백테스트 결과 (+3.044%) 와 실전 차이 검증

3. **`predict()` 의 `news_score` 기능 V4 에 포함?**  
   - 현재 V4: 뉴스 점수 미사용 (백테스트 기반)
   - 옵션: V4 score==3 인데 뉴스 강력하면 STRONG_BUY 승격 가능

4. **운영 모드 Mode A vs Mode B?**  
   - Mode A (score==4 만): 안전, CAGR +43.72%
   - Mode B (4 우선 + 3 보충): 공격적, CAGR +61.56%
   - 현재 권고: Mode A

---

## 10. 결론

- **검증 트랙 9단계 (`_v_19` ~ `_v_27`) 완료** — 운영 채택 가능 수준의 신뢰도
- **Stage 1+2 패치는 회귀 위험 0** — 기존 코드 무수정, 신규 메서드만 추가
- **외부 영향 범위 매우 좁음** — `predict()` 호출 2곳, `cb_score` 별개 시스템
- **Stage 3 마이그레이션은 운영 검증 후** — 즉시 적용 비권장

원칙 4대 모두 준수 가능한 안전한 패치 설계.
