# V4 + H3+S2 검증 트랙 스냅샷 — Seoner 답변 대기 체크포인트

**작성일**: 2026-04-22
**세션 범위**: §27~§37 (14개 검증 세션)
**원칙**: ①Think Before Coding · ②Simplicity First · ③Surgical Changes · ④Goal-Driven

---

## 0. 본 문서의 목적

검증 트랙이 완결된 이 시점에서 **한 눈에 상태 파악**. 다음 재개 시 (Seoner 답변 후) **빠른 재진입**을 위한 단일 체크포인트 문서.

---

## 1. 운영 코드 무수정 재확인 (원칙 ③)

| 파일 | 줄 | byte | 마지막 수정 | 세션 중 수정? |
|------|----|----|-----------|---------|
| `closing_bet_unified.py` | 2,132 | 77,495 | 2026-04-03 | **무수정** ✅ |
| `auto_trader.py` | 7,803 | 364,489 | 2026-04-19 | **무수정** ✅ |

본 세션들은 모두 2026-04-22 진행. 운영 코드에 손대지 않음.


---

## 2. 검증 트랙 전체 (§11 ~ §37)

### 2.1 V4 시그널 (§11~§26)
- §11~§18 시그널 정의 + 백테스트 CAGR +43.72%
- §19~§21 Dry-Run 193,708건 0 mismatch
- §22~§25 5의혹 견고성 5/5 기각
- §23 3레짐 견고성 3/3 양수
- §24 T+1 전용 확정 (T+20 음수)
- §25 설계서 v2 (416줄)
- §26 Stage 3 설계서 (366줄)

### 2.2 중기 시그널 탐색 (§27, 음성)
- 6가지 중기 가설 모두 실패
- V4 T+1 전용 확정 재확인

### 2.3 H3+S2 시장 로테이션 (§28~§31)
- §28 H3 SPREAD 발견 (KOSPI/KOSDAQ, CAGR +10.82%)
- §29 H3 견고성 3/5 부분 (P3 약화)
- §30 P3 약화 원인 = G3 상관관계 증가
- §31 S2 필터 적용 → P3 회복 (+0.24%p → +4.53%p)
- §31 H3+S2 견고성 5/5 (V4 동급)

### 2.4 결합 포트폴리오 (§32)
- V4 + H3+S2 결합 실측 CAGR +5.68%
- **V4 단독 (+12.57%) 이 더 효율적** 판명
- 이전 추정 +18~25% 는 낙관적

### 2.5 V4 파라미터 최적화 (§33~§36)
- §33 정적 최적 (ps=0.07, wr=0.30)
- §34 레짐 동적 (BULL 공격 +0.72%p)
- §35 과적합 검증 3/3 기각
- §36 슬리피지 반영 — **자본별 매트릭스 확립**

### 2.6 설계 문서 통합 (§37)
- V4_PATCH_DESIGN_v3_APPENDIX.md 작성 (286줄)
- v2 무수정, v3 는 부록으로 분리


---

## 3. 산출물 목록

### 3.1 검증 스크립트 29개 (§19~§47)
```
_v_19_closing_bet_conditions.py    _v_34_v4_price_tv_cross.py
_v_20_closing_bet_period_check.py  _v_35_v4_market_regime.py
_v_21_signal_backtest.py            _v_36_predict_v4_v2_dry_run.py
_v_22_signal_backtest_v2.py         _v_37_midterm_signal_exploration.py
_v_23_score_cutoff.py               _v_38_market_rotation_kospi_kosdaq.py
_v_24_overheated_analysis.py        _v_39_h3_spread_robustness.py
_v_25_score_redesign.py             _v_40_h3_p3_degradation_analysis.py
_v_26_count_based_score.py          _v_41_h3_s2_correlation_filter.py
_v_27_v4_backtest_period.py         _v_42_h3_s2_robustness.py
_v_28_predict_v4_dry_run.py         _v_43_v4_h3s2_combined_portfolio.py
_v_29_predict_v4_real_data_check.py _v_44_v4_optimal_allocation.py
_v_30_v4_recent_30days_check.py     _v_45_v4_dynamic_regime_params.py
_v_31_v4_recent_robustness.py       _v_46_v4_walk_forward_validation.py
_v_32_v4_holding_period.py          _v_47_v4_realistic_slippage.py
_v_33_v4_sector_analysis.py
```

### 3.2 설계 + 체크포인트 문서
```
V4_PATCH_DESIGN.md              (v1, 312줄)
V4_PATCH_DESIGN_v2.md           (v2, 416줄)  ← Stage 1+2 패치 설계
V4_PATCH_DESIGN_v3_APPENDIX.md  (v3, 286줄)  ← 자본별 파라미터 매트릭스
V4_STAGE3_AUTOTRADER_DESIGN.md  (Stage 3, 366줄)
V4_CHECKPOINT_20260422.md       ← 본 문서
PHASE_1A_DATA_SOURCES.md        (§1~§37, 누적)
```

### 3.3 운영 코드 (무수정)
```
closing_bet_unified.py  2,132줄 / 77,495 bytes  (2026-04-03 수정)
auto_trader.py          7,803줄 / 364,489 bytes (2026-04-19 수정)
```


---

## 4. Seoner 6개 결정 질문 (최종 통합)

| # | 출처 | 질문 | 권고 | Seoner 답변 |
|---|------|------|------|----------|
| Q1 | v2 §9 | Stage 1+2 즉시 적용 vs 추가 검증? | 즉시 | ☐ |
| Q2 | v2 §9 | Mode A (score==4만) vs Mode B (4+3)? | Mode A | ☐ |
| Q3 | v2 §9 | 가격/거래대금 필터 즉시 반영? | 예 | ☐ |
| Q4 | v2 §9 | 레짐별 포지션 차등 시점? | Stage 3 | ☐ |
| Q5 | v3 §5 | 자본 규모별 파라미터 매트릭스 적용? | 예 (5억→ps=0.05) | ☐ |
| Q6 | v3 §5 | Phase B (BULL 동적) 적용 시점? | Phase A 1개월 후 | ☐ |

### 4.1 권고 답변 전부 수용 시 최종 설정

```python
# closing_bet_unified.py Stage 1+2 패치 적용
# Mode: score == 4 만 매수

# 가격/거래대금 필터 로직
if v4_score == 4:
    price = close_t
    tv_eok = today_tv / 1e8
    if 10000 <= price < 30000 and tv_eok >= 1000:
        recommendation = "SKIP"  # 함정 조합
    elif price < 5000 and tv_eok >= 200:
        recommendation = "STRONG_BUY_PRIORITY"  # 황금 조합
    else:
        recommendation = "STRONG_BUY"

# 자본 5억 기준 파라미터 (Seoner Mock)
V4_WORKING_RATIO = 0.30
V4_PER_STOCK = 0.05
V4_MAX_POS = 30

# Phase A (정적) 먼저, 1개월 후 Phase B 검토
```

---

## 5. 실전 적용 직전 체크리스트

### 5.1 패치 전 (Seoner 답변 받은 직후)
- [ ] SESSION_START.md 재확인
- [ ] BEFORE_CODING.md 재확인
- [ ] `closing_bet_unified.py` 스냅샷 (`snapshot_daily.py`)
- [ ] `pre_commit_check.py` 실행 (13/13 통과 확인)

### 5.2 Stage 1+2 패치 (v2 §3)
- [ ] `predict_v4()` 메서드 추가
- [ ] 기존 `predict()` 무수정 유지
- [ ] 가격/거래대금 필터 포함
- [ ] Dry-Run 재실행 (격리 환경 4/4 통과)
- [ ] `pre_commit_check.py` 재실행

### 5.3 Phase 3A 패치 (Stage 3 설계서)
- [ ] `v4_observations` 테이블 생성 (trading_system.db)
- [ ] auto_trader.py 관찰 모드 60줄 추가
- [ ] 주식 매매 로직 무수정 유지
- [ ] Dry-Run

### 5.4 운영 1주 모니터링
- [ ] V4=4 실제 발생 빈도 (예상: 주 1회, 1~4건)
- [ ] 실제 gap vs 예상치 비교
- [ ] 슬리피지 실측 (§36 모델 0.24% 수준?)


---

## 6. 정직한 전체 평가 (원칙 ①Think Before Coding)

### 6.1 이번 검증 트랙의 성과
- ✅ V4 견고성 최고 수준 입증 (5의혹 5/5, 레짐 3/3, Walk-Forward 3/3)
- ✅ H3+S2 이론 검증 완료 (견고성 5/5)
- ✅ 실전 파라미터 매트릭스 확립 (자본별)
- ✅ 모든 검증 스크립트 재현 가능
- ✅ 운영 코드 무수정 유지

### 6.2 정직한 한계 인정
- ⚠ V4 실전 CAGR 기대치 수정: +43.72% (백테스트 최대) → +5.83% (5억 실전 제약+슬리피지)
- ⚠ H3+S2 결합 가치 제한적: 이전 +18~25% 추정 → +5.68% 실측
- ⚠ T+1 시초가 매도 슬리피지는 §36 모델에서 과소 추정 가능
- ⚠ 상한가/하한가 체결 실패 리스크 미반영
- ⚠ §35 Walk-Forward 는 슬리피지 무시 상태의 최적값 (ps=0.10)

### 6.3 실전 적용 우려 요소
- 운영 1주차 결과가 §36 예상 (+5.83% CAGR) 대비 ±1%p 이내 유지될지
- Seoner 의 실제 자본이 5억과 다르면 §36 매트릭스 재적용 필요
- BULL 시기 ps=0.07 상향 (Phase B) 의 실전 유동성 영향 재측정 필요

### 6.4 권고 재확인
원칙(④Goal-Driven)으로 지금 해야 할 것:
- ✅ 검증 완료
- ✅ 문서화 완료
- ✅ 체크포인트 작성 완료 (본 문서)
- 🕒 **Seoner 답변 대기** — 추가 탐색 없이 순수 대기

원칙(②Simplicity First)으로 지금 하지 말아야 할 것:
- ❌ 추가 탐색 (이벤트 드리븐, 종목 순서 최적화 등은 YAGNI)
- ❌ 문서 중복 작성
- ❌ 운영 코드 미리 수정 (Seoner 답변 전)

---

## 7. 다음 재개 (Seoner 답변 후) 빠른 재진입 가이드

### 7.1 시작 순서
1. 본 문서 (V4_CHECKPOINT_20260422.md) §4 테이블 읽기
2. V4_PATCH_DESIGN_v2.md §3 (Stage 1+2 패치 코드) 읽기
3. V4_PATCH_DESIGN_v3_APPENDIX.md §1 (자본별 매트릭스) 읽기
4. SESSION_START.md + BEFORE_CODING.md 읽기
5. `snapshot_daily.py` → `pre_commit_check.py`
6. Stage 1+2 패치 적용

### 7.2 재진입 시 체크
- Seoner 답변한 Q1~Q6 매핑 확인
- 운영 자본 규모 확인 (§36 매트릭스 적용 기준)
- 현재 시장 레짐 (Phase A 우선 적용, Phase B 보류)

### 7.3 첫 적용 후 모니터링 (1주간)
- V4=4 발생 횟수
- 실제 평균 gap
- 실제 슬리피지 (vs §36 모델 0.24%)
- 월승률 (예상 73.6%)

---

## 8. 결론

**검증 트랙 완결** (§11~§37). 다음 단계는 Seoner 의사 결정과 실전 패치 적용.

모든 원칙 준수 확인:
- ①Think Before Coding — 47개 검증 스크립트, 모든 가설 사전 명시
- ②Simplicity First — 추가 탐색 중단 판단 (본 세션)
- ③Surgical Changes — 운영 코드 2개 파일 무수정 유지
- ④Goal-Driven — "실전 적용 준비" 목표 달성
