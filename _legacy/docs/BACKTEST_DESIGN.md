# Phase 2 백테스트 엔진 설계 (수정판)

## 0. 근본적·원칙적 방향

- **원래 시스템 설계 존중**: 스크리너 → 전략 2단계 구조
- **정합성·무결성**: 각 전략 코드 수정 금지. 데이터 레이어만 교체
- **실전 일치**: 백테스트 결과가 실제 시스템의 과거 실행 결과와 동일
- **운영 DB 오염 방지**: 별도 `backtest_long.db`

## 1. 원래 설계 흐름 (실측 확인 완료)

### screener_v67.ScreenerV12.run() 실측 흐름

```
[1단계] scan_trading_value_rank(top_n=200)  ← 네이버 API
  ↓
[2단계] _calc_new_high_from_candidates(...)  ← 60일 신고가 추가
  ↓ (중복 제거)
[3단계] analyze_stock(code, name, base_data)
        ├ get_ohlcv(code)  ← 최근 90일 OHLCV
        ├ calculate_closing_bet_score(ohlcv, code)
        │   ├ check_condition1  (정배열+장대양봉+거래대금)
        │   ├ check_condition2  (60일 신고가+조정)
        │   ├ check_condition3  (눌림목 돌파)
        │   ├ check_condition4  (기준봉)
        │   └ calculate_fundamental_score(code)  ← 펀더멘털 가산점
        ├ 기술적 지표 (RSI/ATR/MA)
        └ 종합 total_score 계산
  ↓
[4단계] _save_to_db → scanned_targets_v2 테이블
```

### 각 전략 스캔 실측 흐름 (strategy_rsi 샘플)

```
[1단계] get_stock_list()
  SELECT code, name FROM scanned_targets_v2
  WHERE date = (SELECT MAX(date) FROM scanned_targets_v2)
  ← 스크리너 결과 사용
  ↓
[2단계] 각 종목별 analyze_stock(code, name)
        ├ get_ohlcv(code, days=60)
        ├ calculate_rsi(df)
        ├ detect_oversold_bounce(rsi)
        ├ detect_divergence(df, rsi)
        └ score 계산 → status(STRONG_BUY/BUY/WATCH)
  ↓
[3단계] rs_targets_v2 / rsi_targets_v2 등 저장
```

**핵심: 14개 전략 모두 `FROM scanned_targets_v2 WHERE date = MAX(date)`
= 스크리너 결과 universe 공유**

## 2. 백테스트 어댑터 설계

### 2.1 BacktestContext 클래스 (backtest_adapter.py)

```
with BacktestContext(asof_date="20200301") as ctx:
    # 1. 어댑터 install 상태
    
    # 2. 스크리너 실행 (원본 그대로)
    screener = ScreenerV12(mode="EOD")
    screener.run(save_db=True)
    # → scanned_targets_v2가 아니라
    #   backtest_screener_results로 리다이렉트되어 저장됨
    
    # 3. 각 전략 실행
    RSIBot().run(limit=50)
    # → rs_targets_v2가 아니라
    #   backtest_strategy_results로 리다이렉트
    
# context exit: 원 함수 복원
```

### 2.2 교체 대상 함수 (실측 확인된 6개)

1. `market_utils.get_last_business_day()` → `asof_date` 반환
2. `screener_v67.get_latest_trading_day()` → `asof_date` 반환
3. `krx_data.KRXDataClient.get_stock_ohlcv(code, days)` → ohlcv_long.db 조회
4. `krx_data.KRXDataClient.get_market_ohlcv(date, market)` → ohlcv_long.db 조회
5. `krx_data.KRXDataClient.get_market_ohlcv_by_date(from, to, ticker)` → ohlcv_long.db
6. `fdr.DataReader(code, start, end)` → ohlcv_long.db (strategy_rs_v2 대비)

### 2.3 SQL 리다이렉션

전략/스크리너가 실행하는 SQL을 SQLite에서 교체:
- `FROM scanned_targets_v2 WHERE date = MAX(date)`
  → `FROM backtest_screener_results WHERE asof_date = ?`
- `INSERT INTO xxx_targets_v2 ...`
  → `INSERT INTO backtest_strategy_results (..., strategy=?, asof_date=?)`

구현 방식: **BacktestContext가 `sqlite3.connect(DB_PATH)`를 가로채서
`backtest_long.db`를 반환하고, 테이블 이름을 alias로 매핑**

### 2.4 스크리너에서 비활성화할 요소

- `calculate_fundamental_score()`: 과거 PER/ROE 스냅샷 없음 → **0점 반환하도록 패치**
- `use_extra_analysis=False`: 기본값 유지
- `scan_new_high_kiwoom`, `_scan_trading_value_kiwoom`: 키움 API 미사용 (EOD 모드)
- `stock_issue_checker.is_hard_exclude`: 과거 관리종목 데이터 없음 → 무시

### 2.5 거래대금 상위 과거 재현

원본 `_scan_trading_value_pykrx`는 네이버 API로 당일 거래대금 상위 조회.
백테스트에선 `ohlcv_long.db`의 해당 asof_date 거래대금(= close × volume) 정렬:

```sql
SELECT code, close*volume AS tv,
       open, high, low, close, volume
FROM daily_ohlcv_long
WHERE date = :asof_date
  AND volume > 0 AND close BETWEEN low AND high
ORDER BY tv DESC
LIMIT 200
```

## 3. 백테스트 DB 스키마

### backtest_long.db

#### backtest_screener_results
- 스크리너 통과 종목 (scanned_targets_v2 대체)
- PRIMARY KEY (asof_date, code)
- 컬럼: asof_date, code, name, price, change_pct, volume,
       cb_cond1~4, cb_score, cb_grade, tech_score, total_score,
       ma_alignment, rsi, volume_ratio, atr_pct, gap_from_high,
       analysis_detail, created_at

#### backtest_strategy_results
- 각 전략 분석 결과 (rs_targets_v2, rsi_targets_v2 등 통합)
- PRIMARY KEY (asof_date, code, strategy)
- 컬럼: asof_date, code, strategy, score, status, signal_type,
       detail(JSON), created_at

#### backtest_performance_long
- 최종 수익률 결합 결과
- PRIMARY KEY (asof_date, code, strategy)
- 컬럼: asof_date, code, strategy, signal_type, score,
       entry_price, ret_1d, ret_5d, ret_20d, ret_60d,
       max_gain_20d, max_loss_20d,
       regime(bull/sideways/bear), era, created_at

#### strategy_regime_summary
- 집계 테이블
- PRIMARY KEY (strategy, regime, era)
- 컬럼: strategy, regime, era, sample_count,
       win_rate_1d/5d/20d, avg_ret_1d/5d/20d/60d,
       sharpe_20d, max_dd, profit_factor, calmar, updated_at

## 4. 구현 순서

### Phase 2.1: 어댑터 구현
- backtest_adapter.py: BacktestContext + Reader
- SQL 리다이렉션 메커니즘
- 스모크 테스트 (asof_date=최근 영업일 → 결과가 운영 시스템 결과와 일치 확인)

### Phase 2.2: 스크리너 단계 백테스트
- asof_date 1개에 대해 ScreenerV12.run() → backtest_screener_results 저장
- 결과 검증: 원본 scanned_targets_v2와 유사한 분포인가

### Phase 2.3: 전략 단계 백테스트
- asof_date 1개 × 전략 1개 (strategy_rsi)
- 결과 검증: 원본 rsi_targets_v2 결과와 유사한가

### Phase 2.4: 수익률 계산
- backtest_performance_long 채우기
- 1d/5d/20d/60d 각 수익률 계산

### Phase 2.5: 전량 백테스트
- 30년 (1996~2026) × 월 20회 영업일 × 14 전략
- 예상 수만 건 (asof_date) × 200 후보 × 14 전략 = 수억 건 평가

### Phase 2.6: 결과 집계
- strategy_regime_summary
- 국면별/시기별 매트릭스
- v7 fundamental_grade 설계 결정 근거 확보

## 5. 검증 원칙

1. **어댑터 정확성**: asof_date = 최근 영업일 → 운영 시스템 결과와 결과 매칭 (수작업 20건)
2. **수익률 정합성**: entry_price(asof_date 종가) + ret_5d → 5일 후 종가와 일치
3. **국면 분류 정합성**: 이미 Phase 1에서 검증 완료 (KOSPI 20d 수익률)
4. **look-ahead 방지**: 어떤 쿼리도 asof_date 초과 날짜 데이터 반환 금지
