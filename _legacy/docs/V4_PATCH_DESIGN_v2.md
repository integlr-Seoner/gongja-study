# V4 카운트 기반 점수 시스템 — 최종 패치 설계서 v2

**작성일**: 2026-04-22  
**문서 버전**: v2 (v1 → 검증 5차례 추가 후 통합)  
**대상 파일**: `D:\StockAnalyst\closing_bet_unified.py` (70,896 chars)  
**근거**: `PHASE_1A_DATA_SOURCES.md` §11~23 (전체 검증 트랙)  
**원칙**: ①Think Before Coding · ②Simplicity First · ③Surgical Changes · ④Goal-Driven

---

## 0. 요약 (Seoner가 먼저 읽을 부분)

### V4 시그널 정의 (확정)
```
4조건 각 1점 → 0~4 정수
  C1. 정배열(MA5>MA10>MA20) + 장대양봉(body/range > 0.6)
  C2. 60일 신고가 (today.high > prev60.max)
  C3. 거래대금 3배↑ (today.tv / avg20.tv >= 3.0)
  C4. 종가 위치 95%↑ ((close-low)/(high-low) >= 0.95)
```

### 운영 채택 결정 사항

| 항목 | 결정 |
|------|------|
| 메인 시그널 | **V4 score == 4** 만 매수 (Mode A) |
| 보유기간 | **T+1 시초가 매도** (필수 — _v_32 입증) |
| 자본 운용 | 총 자본의 30% 운용, 종목당 5% 한도 |
| 최대 포지션 | 30개 (BULL/SIDEWAYS), 15개 (BEAR) |
| 가격 필터 | 10,000~30,000원 + 거래대금 1000억+ 종목 **SKIP** |
| 우선 매수 | 가격 < 5,000원 + 거래대금 200억+ 종목 |
| Circuit Breaker | -3%/1일, -5%/7일, -10%/30일 중단 |

### 예상 성과 (검증된 수치)

| 지표 | 백테스트 (13년) | 최근 1개월 실전 |
|------|---------------|--------------|
| 평균 gap | +3.504% | +6.663% |
| realized | +3.044% | +6.203% |
| 승률 | 63.1% | 76.2% |
| CAGR | +43.72% | (+120% 연환산, 강세장 효과 포함) |
| MDD | -1.6% | - |
| Sharpe | 8.90 | - |

---

## 1. 검증 트랙 요약 (9 스테이지, 모두 통과)

| # | 스테이지 | 스크립트 | 결과 |
|---|---------|---------|------|
| 1 | 기본 신호 발굴 | `_v_19`~`_v_22` | C1+C2+V, C2+V+P 등 시그널 4종 |
| 2 | 시기 안정성 | `_v_20` | STABLE, cv 0.14~0.15 |
| 3 | 백테스트 v2 | `_v_22` | CAGR +30.98%, MDD -3.6% |
| 4 | 점수 시스템 | `_v_23`~`_v_26` | V4 카운트가 가중치 합산 압도 |
| 5 | V4 백테스트 | `_v_27` | CAGR **+43.72%**, MDD **-1.6%**, Sharpe **8.90** |
| 6 | 패치 정합성 | `_v_28`~`_v_29` | 193,708건 **0 mismatch** |
| 7 | 실전 1개월 | `_v_30`~`_v_31` | realized **+6.203%**, 5의혹 기각 |
| 8 | 보유기간 | `_v_32` | T+1 Sharpe **0.407**, T+20 음수 |
| 9 | 가격/거래대금 | `_v_33`~`_v_34` | 황금 조합 realized +6.405% |
| 10 | 시장 레짐 | `_v_35` | 3레짐 전부 양수, BEAR +1.306% |

---

## 2. 영향 범위 (실측 확인)

### 2.1 외부 호출처 (2곳 만)
- `D:\StockAnalyst\api\legacy_scan_ext_api.py:947` — `predictor.predict(code, df, news_score=0)`
- `D:\StockAnalyst\api\legacy_scan_ext_api.py:1051` — 동일 패턴
- 사용 키 5개: `total_score`, `grade`, `expected_gap`, `breakdown`, `recommendation`

### 2.2 내부 함수 (외부 호출 0)
- `_score_chart_pattern`, `_score_trading_value`, `_score_close_position`
- `_determine_grade`, `_get_recommendation`

### 2.3 별개 시스템 (영향 없음)
- `closing_bet_filter.cb_score` (A/B/C/D 4등급)
- `screener_v67.cb_score`
- `auto_trader.py` — 연동 경로 별도 설계 필요 (Stage 4)

---

## 3. Stage 1: 신규 메서드 `predict_v4()` 추가

### 3.1 삽입 위치
`closing_bet_unified.py` 의 기존 `predict()` 메서드 직후 (현재 file offset 약 55,500).

### 3.2 추가 코드 (90줄)

```python
def predict_v4(self, code: str, ohlcv: pd.DataFrame) -> dict:
    """V4 카운트 기반 점수 (0~4 정수)
    
    4조건 각 1점:
        C1. 정배열(MA5>MA10>MA20) + 장대양봉(body/range > 0.6)
        C2. 60일 신고가
        C3. 거래대금 3배↑
        C4. 종가 위치 95%↑
    
    검증 (PHASE_1A_DATA_SOURCES.md §17~23):
        score==4: realized +3.044% (승률 63.1%, CAGR +43.72%, MDD -1.6%)
        실전 1개월: realized +6.203% (승률 76.2%)
        모든 시장 레짐에서 양수 (BULL/SIDEWAYS/BEAR)
    
    Returns (기존 predict() 호환 + v4 전용 키):
        {
            'code': str,
            'v4_score': int (0~4),
            'v4_grade': str ('STRONG_BUY'/'BUY'/'WATCH'),
            'v4_conditions': dict (조건별 bool),
            'v4_price_filter': str ('PRIORITY'/'SKIP'/'NORMAL') — 가격/거래대금 필터,
            'expected_gap': str,
            'recommendation': str,
            # 기존 predict() 호환 (마이그레이션용)
            'total_score': int (v4_score * 25, 0~100),
            'grade': str (HIGH/MEDIUM/LOW/VERY_LOW),
            'breakdown': dict,
        }
    """
    if len(ohlcv) < 60:
        return self._empty_result_v4(code, "데이터 부족")
    
    # 4조건 평가
    cond1 = self._is_align_and_big_candle(ohlcv)
    cond2 = self._is_60day_new_high(ohlcv)
    cond3 = self._get_volume_value_ratio(ohlcv) >= 3.0
    cond4 = self._get_close_position(ohlcv) >= 0.95
    
    v4_score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
    
    # 가격/거래대금 필터 (_v_34 결과 반영)
    price = float(ohlcv['Close'].iloc[-1])
    vol = float(ohlcv['Volume'].iloc[-1])
    tv_eok = (price * vol) / 1e8  # 거래대금 억원
    
    if v4_score == 4:
        # 함정 조합: 중-고가(10k~30k) + 초대형(1000억+) → SKIP
        if 10000 <= price < 30000 and tv_eok >= 1000:
            price_filter = 'SKIP'
            grade = 'SKIP'
            gap = '회피'
            rec = '함정 조합 (중-고가 + 초대형 거래대금, realized -0.107%)'
            legacy_grade = 'LOW'
        # 황금 조합: 저가~저-중(5k 미만) + 대형 이상(200억+)
        elif price < 5000 and tv_eok >= 200:
            price_filter = 'PRIORITY'
            grade = 'STRONG_BUY'
            gap = '5-7%+'
            rec = '우선 매수 (황금 조합, realized +5~6%)'
            legacy_grade = 'HIGH'
        else:
            price_filter = 'NORMAL'
            grade = 'STRONG_BUY'
            gap = '3-5%+'
            rec = '적극 매수 (4조건 충족, realized +3.044%)'
            legacy_grade = 'HIGH'
    elif v4_score == 3:
        price_filter = 'NORMAL'
        grade = 'BUY'
        gap = '0-1%'
        rec = '보조 매수 (realized +0.370%)'
        legacy_grade = 'MEDIUM'
    else:
        price_filter = 'NORMAL'
        grade = 'WATCH'
        gap = '불확실'
        rec = '관망 (조건 부족)'
        legacy_grade = 'LOW' if v4_score == 2 else 'VERY_LOW'
    
    return {
        'code': code,
        'v4_score': v4_score,
        'v4_grade': grade,
        'v4_conditions': {
            'align_and_big_candle': bool(cond1),
            'new_high_60d': bool(cond2),
            'volume_value_3x': bool(cond3),
            'close_position_95': bool(cond4),
        },
        'v4_price_filter': price_filter,
        'expected_gap': gap,
        'recommendation': rec,
        # 기존 predict() 호환 키
        'total_score': v4_score * 25,
        'grade': legacy_grade,
        'breakdown': {
            'v4_chart': (int(cond1) + int(cond2)) * 25,
            'v4_volume': int(cond3) * 25,
            'v4_position': int(cond4) * 25,
            'news': 0,
        },
    }

def _empty_result_v4(self, code: str, reason: str) -> dict:
    return {
        'code': code, 'v4_score': 0, 'v4_grade': 'WATCH',
        'v4_conditions': {}, 'v4_price_filter': 'NORMAL',
        'expected_gap': '불확실', 'recommendation': reason,
        'total_score': 0, 'grade': 'VERY_LOW', 'breakdown': {},
    }
```

---

## 4. Stage 2: 헬퍼 메서드 4개 추가

### 4.1 삽입 위치
`predict_v4()` 직후.

### 4.2 추가 코드 (60줄)

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
    return bool(h[-1] > h[-61:-1].max())

def _get_volume_value_ratio(self, ohlcv: pd.DataFrame) -> float:
    """오늘 거래대금 / 직전 20일 평균 거래대금"""
    c = ohlcv['Close'].values
    v = ohlcv['Volume'].values
    if len(c) < 21:
        return 0.0
    today_tv = c[-1] * v[-1]
    avg20_tv = (c[-21:-1] * v[-21:-1]).mean()
    return float(today_tv / avg20_tv) if avg20_tv > 0 else 0.0

def _get_close_position(self, ohlcv: pd.DataFrame) -> float:
    """종가의 일중 위치 (0=저가, 1=고가)"""
    h = float(ohlcv['High'].values[-1])
    l = float(ohlcv['Low'].values[-1])
    c = float(ohlcv['Close'].values[-1])
    rng = h - l
    return (c - l) / rng if rng > 0 else 0.0
```

---

## 5. Stage 3: auto_trader 통합 (별도 작업)

### 5.1 목적
실시간 스캔에서 V4=4 종목 자동 매수 + T+1 시초가 자동 매도.

### 5.2 통합 지점 (추정, 실측 필요)
- `auto_trader.py` 의 매수 시그널 생성 루프 (약 L1,086~1,188)
- 현재 `closing_bet` 관련 코드 대체 또는 병행

### 5.3 필요 기능
1. V4=4 종목 추출 (`predict_v4()` 호출)
2. 가격/거래대금 필터 적용 (PRIORITY/SKIP)
3. 레짐 체크 (BEAR 시 max_positions=15)
4. 종목당 5% 한도 / 30 포지션 max
5. T+1 시초가 매도 예약 (지정가 또는 시장가)
6. Circuit Breaker 감시

### 5.4 사전 조건
- Stage 1+2 적용 + 1주일 이상 운영 검증
- `auto_trader.py` 의 현재 매매 로직 실측 후 통합 지점 확정
- CB, 위험 관리, 심리 가드 기존 로직과 충돌 확인

---

## 6. Stage 4: 마이그레이션 (선택, 추후)

### 6.1 `legacy_scan_ext_api.py` 의 2곳 수정
```python
# L947, L1051 현재:
pred = predictor.predict(code, df, news_score=0)
if pred and pred.get('total_score', 0) >= 40:

# 마이그레이션 후:
pred = predictor.predict_v4(code, df)
if pred and pred.get('v4_score', 0) >= 3:  # BUY + STRONG_BUY
```

### 6.2 현 호환 수준
`predict_v4()` 가 이미 `total_score = v4_score * 25` 환산을 제공하므로:
- v4_score=2 → total_score=50 (≥40 통과)
- v4_score=1 → total_score=25 (미통과)
- 사실상 **마이그레이션 없이도 기존 호출이 v4_score >= 2 로 작동**

단, 현재 `predict()` 의 HIGH(≥80) 기준과 v4_score=4 의 total_score=100 가 매핑되는 방식은 주의 필요.

---

## 7. 적용 절차 (체크리스트)

### 7.1 Phase A — 코드 패치 (Stage 1+2)
1. [ ] `closing_bet_unified.py` 백업 (`closing_bet_unified.backup.py`)
2. [ ] `predict()` 직후에 §3 Stage 1 코드 90줄 추가
3. [ ] `predict_v4()` 직후에 §4 Stage 2 코드 60줄 추가
4. [ ] `py_compile` 구문 검증
5. [ ] 기존 `predict()` 호출 테스트 (회귀 확인)
6. [ ] `pre_commit_check.py` 13/13 통과 확인

### 7.2 Phase B — 실전 검증
1. [ ] 임의 종목 10개에 대해 `predict_v4()` 직접 호출 결과 출력
2. [ ] 출력 스키마가 §3.2 설계와 일치하는지 확인
3. [ ] `total_score` 환산값 (0/25/50/75/100) 정상 확인
4. [ ] 가격 필터 동작 확인 (SKIP/PRIORITY/NORMAL 각 케이스)

### 7.3 Phase C — 운영 배포
1. [ ] Git 커밋 (메시지 템플릿 포함)
2. [ ] `snapshot_daily.py` 로 스냅샷 저장
3. [ ] 운영 모니터링 1주일 (V4=4 종목 발생 + 실제 갭)
4. [ ] 결과가 설계서 예상치와 일치하는지 비교

### 7.4 Phase D — Stage 3 착수 결정
- Phase C 1주일 결과 검토 후 진행 여부 결정
- 예상치 +80% 이내면 진행, 그 이하면 원인 분석

---

## 8. 회귀 위험 평가 (v1 대비 갱신)

| 위험 카테고리 | 평가 | 근거 |
|--------------|------|------|
| 기존 `predict()` 동작 변경 | **0** | 무수정 |
| 기존 호출처 (2곳) 호환성 | **0** | v4_score*25 환산으로 `total_score` 필드 유지 |
| `closing_bet_filter` 영향 | **0** | 별개 시스템 |
| `screener_v67` 영향 | **0** | 별개 시스템 |
| ML 모델 학습 데이터 영향 | **0** | DB 무변경 |
| 신규 메서드 자체 버그 | **매우 낮음** | Dry-run 4/4 + 실데이터 193,708건 0 mismatch |
| 운영 중 예상 안 됨 | **매우 낮음** | 13년 + 실전 1개월 + 3레짐 검증 |

**종합: 회귀 위험 사실상 0**

---

## 9. Seoner 결정 필요 사항 (4개)

### Q1. Stage 1+2 즉시 적용 vs 추가 검증 후 적용?
- **즉시 권고 이유**: 193,708건 0 mismatch + 실전 1개월 +6.203% + 3레짐 통과
- 추가 검증 옵션: 최근 3개월로 확장 / 특정 기간 스팟 체크

### Q2. Mode A (score==4만) vs Mode B (4+3 보충)?
- **Mode A 권고**: Sharpe 8.90, PF 4.89, MDD -1.6% (가장 안정)
- Mode B: CAGR +61.56%, PF 2.34, MDD -2.6% (더 공격적)

### Q3. 가격/거래대금 필터 즉시 반영?
- **권고: 예**
- 함정 조합(-0.107%) 회피 + 황금 조합(+6.405%) 우선 매수
- §3.2 코드에 이미 포함

### Q4. 레짐별 포지션 차등 즉시 반영?
- **권고: Stage 3 auto_trader 통합 시점에서 반영**
- `predict_v4()` 자체는 레짐 무관 (범용)
- auto_trader 레벨에서 `if regime == 'BEAR': max_pos = 15` 처리

---

## 10. 미해결 의혹 (투명성)

### 10.1 실전 +6.203% vs 백테스트 +3.044% 의 큰 차이
- 백테스트 BULL 기간 realized +2.955%
- 실전 (BULL 추정) +6.203%
- 차이 +3.25%p 의 설명: **변동성 확대 + 장대양봉 패턴 급증 시장** 추정
- 운영 채택 후 1~3개월 모니터링으로 검증 필요

### 10.2 BEAR 샘플 부족 (N=26)
- BEAR realized +1.306% 양수지만 통계 유의도 제한
- 2008년 금융위기, 2020년 코로나 급락 등 극단 BEAR 미포함
- 운영 시 BEAR 보수적 접근 (max_positions 절반)

### 10.3 섹터 분석 불가
- 섹터 매핑 11% 만 (1,472건 중 157개)
- V4 의 섹터 편향 여부 확정 불가
- 추가 섹터 데이터 수집 후 재검증 필요

---

## 11. 적용 후 권장 후속 작업

| 우선도 | 작업 | 설명 |
|-------|------|------|
| ⭐⭐⭐ | 운영 1주 모니터링 | V4=4 실제 발생 + 갭 결과 비교 |
| ⭐⭐ | auto_trader 통합 (Stage 3) | 자동 매수/매도 구현 |
| ⭐⭐ | dashboard v4_score 표시 | UI 에서 종목별 V4 점수 확인 |
| ⭐ | 섹터 데이터 보강 | 157 → 1,000+ 매핑 확장 |
| ⭐ | T+1 실시간 시초가 주문 | 시장가 vs 지정가 최적화 |
| ⭐ | 중기 보유용 별도 시그널 | V4 외 스윙 트레이딩용 시그널 발굴 |

---

## 12. 최종 결론

**V4 시그널은 9단계 검증을 모두 통과**:
- 시기 안정성 ✅
- 백테스트 CAGR +43.72% ✅
- 실전 1개월 +6.203% ✅
- 3 레짐 (BULL/SIDEWAYS/BEAR) 모두 양수 ✅
- 가격/거래대금 편향 식별 완료 ✅
- 패치 정합성 0 mismatch ✅

**Stage 1+2 패치는 회귀 위험 사실상 0** — Seoner §9 답변 후 즉시 적용 가능.

원칙 4대 (①Think Before Coding · ②Simplicity First · ③Surgical Changes · ④Goal-Driven) 모두 준수한 검증 트랙 완결.
