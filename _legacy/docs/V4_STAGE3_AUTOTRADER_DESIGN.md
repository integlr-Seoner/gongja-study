# V4 Stage 3 — auto_trader 통합 설계서

**작성일**: 2026-04-22  
**대상 파일**: `D:\StockAnalyst\auto_trader.py` (7,803줄, 364KB)  
**전제**: Stage 1+2 (`closing_bet_unified.predict_v4()`) 가 이미 적용된 상태  
**원칙**: ①Think Before Coding · ②Simplicity First · ③Surgical Changes · ④Goal-Driven

---

## 0. 요약

V4 시그널(score==4) 을 auto_trader 의 실시간 매매 흐름에 통합. 매도 로직은 이미 구현됨 — 매수 로직만 보강.

**권고**: `_check_cb_conditions` 결과 옆에 `predict_v4()` 결과를 병행 로깅 → 1~2주 관찰 후 실제 게이트로 승격.

---

## 1. 실측 결과 (auto_trader.py 구조)

### 1.1 매수 흐름 (종가 15:00~15:20)

```
_check_buy_signals (L1313)
  ├─ 매크로 체크 (score >= 20)
  ├─ _get_buy_targets() — scanned_targets_v2 조회
  ├─ _analyze_top_targets_for_today() — 옵션 D 실시간 분석
  ├─ 보유종목/한도/일일손실 체크
  └─ for target in targets:
        ├─ 1차 필터: 하한가/위험종목/급등폭락/내부문제/NXT섹터
        ├─ _check_sector_diversification — 섹터 분산
        ├─ _check_technical_gate — 기술적 게이트키퍼
        ├─ _check_ml_veto — ML Veto
        ├─ [종가배팅만] _check_material_exists — 재료 확인
        ├─ [종가배팅만] _check_cb_conditions — 차트 조건 (cb_cond1/2/3)  ★ V4 진입점
        ├─ [종가배팅만] _check_gap_from_high — 전고점 이격
        ├─ [종가배팅만] _check_wyckoff_upthrust — UT 필터
        ├─ [종가배팅만] _check_upper_shadow_filter — 윗꼬리 매물대
        ├─ _check_resistance_proximity — 저항선 근접
        └─ _queue_order({'action': 'BUY', ...}) — 주문 큐 enqueue
```

### 1.2 매도 흐름 (T+1 시초가) — 이미 구현됨

- **09:00:05**: `_morning_sell_half` — 종가배팅 절반 시장가 매도
- **09:05:00**: `_morning_sell_all` — 종가배팅 잔여 전량 매도
- **15:00~15:25**: 미매도 복구 (force_all=False)

→ V4 통합 시 매도는 **기존 로직 재사용** (수정 불필요)

### 1.3 정규화

L4204: `_VALID_INVESTMENT_TYPES = {'종가배팅', '스윙', '중장기'}` — V4 매수도 `investment_type='종가배팅'` 으로 들어감.

---

## 2. 통합 지점 결정

### 2.1 옵션 비교

| 옵션 | 설명 | 위험 | 선택 |
|------|------|------|------|
| A | `_check_cb_conditions` 내부에 V4 통합 | 기존 cb_cond1/2/3 손상 위험 | ❌ |
| B | `_check_cb_conditions` 호출 직후 V4 병행 호출, 로그만 | 영향 0, 관찰 가능 | ✅ (Phase 3A) |
| C | `_check_cb_conditions` 통과 조건에 V4=4 필수 추가 | cb_cond 대체 완전 | 🕒 (Phase 3B) |
| D | 별도 함수 `_check_v4_buy` 신설 — 병행 매수 | 포지션 이중 진입 위험 | ❌ |

### 2.2 선택: B → C 단계적 승격

**Phase 3A (즉시)**: V4 를 관찰 모드로 병행 — `_check_cb_conditions` 직후 로깅만  
**Phase 3B (1~2주 후)**: Phase 3A 결과 검증되면 V4 를 필수 게이트로 승격

---

## 3. Phase 3A — 관찰 모드 (즉시 적용 가능)

### 3.1 삽입 위치
`auto_trader.py` L1548~1558 (`_check_cb_conditions` 통과 직후)

### 3.2 추가 코드 (약 30줄)

```python
# ★ V4 관찰 로그 (Phase 3A — 판단에는 사용 안 함, 데이터 수집만)
# 검증 기간: 최소 2주 — V4=4 종목의 실제 갭 결과 비교
if investment_type == '종가배팅':
    try:
        from closing_bet_unified import GapUpPredictor
        import pandas as pd
        _v4_predictor = GapUpPredictor()  # 기존 인스턴스 재사용 권장

        # 최근 70일 OHLCV 조회 (V4 는 60일 이상 필요)
        _v4_ohlcv_rows = self._get_recent_ohlcv(code, days=70)
        if _v4_ohlcv_rows and len(_v4_ohlcv_rows) >= 60:
            _v4_df = pd.DataFrame(_v4_ohlcv_rows, columns=[
                'Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            _v4_r = _v4_predictor.predict_v4(code, _v4_df)
            
            # DB 저장 (v4_observations 테이블) — 사후 갭 비교용
            self._log_v4_observation(code, name, _v4_r, price)
            
            # 콘솔 로깅
            if _v4_r['v4_score'] == 4:
                icon = {'PRIORITY': '⭐⭐', 'SKIP': '⛔', 'NORMAL': '⭐'}.get(
                    _v4_r.get('v4_price_filter', 'NORMAL'), '⭐')
                self._log(f"{icon} V4=4 [{_v4_r['v4_grade']}/"
                          f"{_v4_r['v4_price_filter']}]: {name} "
                          f"예상갭 {_v4_r['expected_gap']}")
            elif _v4_r['v4_score'] == 3:
                self._log(f"○ V4=3: {name}")
    except Exception as e:
        # V4 에러는 기존 로직 방해 않음 (Phase 3A 는 관찰만)
        pass
```

### 3.3 신규 DB 테이블 + 헬퍼 메서드

```sql
-- auto_trader 의 DB 에 추가
CREATE TABLE IF NOT EXISTS v4_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_date TEXT NOT NULL,     -- YYYYMMDD
    code TEXT NOT NULL,
    name TEXT,
    v4_score INTEGER NOT NULL,           -- 0~4
    v4_grade TEXT,                       -- STRONG_BUY/BUY/WATCH/SKIP
    v4_price_filter TEXT,                -- PRIORITY/SKIP/NORMAL
    v4_conditions TEXT,                  -- JSON
    close_price REAL,
    cb_conditions_passed INTEGER,        -- _check_cb_conditions 결과 병행 기록
    created_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE (observation_date, code)
);

CREATE INDEX IF NOT EXISTS idx_v4_obs_date ON v4_observations(observation_date);
CREATE INDEX IF NOT EXISTS idx_v4_obs_score ON v4_observations(v4_score);
```

헬퍼 메서드 (+30줄):

```python
def _log_v4_observation(self, code, name, v4_result, price):
    """V4 관찰 로그를 DB 저장 — Phase 3A 검증용"""
    import json
    from datetime import datetime
    try:
        today = datetime.now().strftime('%Y%m%d')
        conn = sqlite3.connect(
            os.path.join(BASE_DIR, 'trading_system.db'), timeout=5)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO v4_observations
                    (observation_date, code, name, v4_score, v4_grade,
                     v4_price_filter, v4_conditions, close_price,
                     cb_conditions_passed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (today, code, name, v4_result['v4_score'],
                  v4_result.get('v4_grade'),
                  v4_result.get('v4_price_filter'),
                  json.dumps(v4_result.get('v4_conditions', {}),
                             ensure_ascii=False),
                  price))
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        self._log(f"V4 관찰 DB 저장 실패: {e}", 'debug')

def _get_recent_ohlcv(self, code, days=70):
    """code 의 최근 N일 OHLCV 조회 (최근순 → 오름차순 재정렬)"""
    try:
        price_db = os.path.join(BASE_DIR, 'stock_data.db')
        conn = sqlite3.connect(price_db, timeout=5)
        try:
            rows = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM daily_prices
                WHERE code = ?
                ORDER BY date DESC LIMIT ?
            """, (code, days)).fetchall()
        finally:
            conn.close()
        return list(reversed(rows))  # 오름차순 (과거 → 현재)
    except Exception:
        return []
```

### 3.4 영향 범위

- 기존 매수 로직: **0 수정**
- 기존 _check_cb_conditions: **0 수정**
- 매도 로직: **0 수정**
- 신규 테이블 (v4_observations): 읽기 전용 관찰 데이터
- 실행 오버헤드: 종목당 약 5~10ms (OHLCV 조회 + V4 계산)

### 3.5 예상 산출 데이터 (2주 후 검증용)

```sql
-- V4=4 종목의 실제 다음날 갭 결과 집계 예시
SELECT 
    v.v4_grade,
    v.v4_price_filter,
    COUNT(*) AS n,
    AVG((p2.open - p1.close) / p1.close * 100) AS actual_gap_pct
FROM v4_observations v
JOIN daily_prices p1 ON v.code = p1.code AND v.observation_date = p1.date
JOIN daily_prices p2 ON v.code = p2.code AND p2.date = (
    SELECT MIN(date) FROM daily_prices WHERE code = v.code AND date > v.observation_date
)
WHERE v.v4_score = 4
GROUP BY v.v4_grade, v.v4_price_filter;
```

---

## 4. Phase 3B — 게이트 승격 (1~2주 후)

### 4.1 조건 (Phase 3A 결과 충족 시)
- V4=4 + NORMAL 실제 갭 평균 >= +2% (설계서 +3% 대비 보수적)
- V4=4 + SKIP 실제 갭 평균 < +2% (함정 조합 입증)
- V4=4 + PRIORITY 실제 갭 평균 >= +4% (우선 매수 가치)

### 4.2 변경 사항
`_check_cb_conditions` 호출 라인을 V4 게이트 + cb_cond 병행으로 변경:

```python
# 기존:
if investment_type == '종가배팅':
    cb_check = self._check_cb_conditions(code)
    if not cb_check.get('passed', False):
        self._log(f"⛔ 차트 조건 미통과: {name} ({cb_check.get('reason', '')})")
        continue

# 변경 후 (Phase 3B):
if investment_type == '종가배팅':
    cb_check = self._check_cb_conditions(code)
    v4_check = self._check_v4_gate(code)  # 신규 헬퍼
    
    # SKIP 조합 절대 차단
    if v4_check.get('filter') == 'SKIP':
        self._log(f"⛔ V4 함정조합 차단: {name}")
        continue
    
    # V4=4 는 cb_cond 우회 허용 (품질 보장)
    if v4_check.get('score') == 4:
        self._log(f"✅ V4=4 게이트 통과: {name} "
                  f"[{v4_check.get('grade')}/{v4_check.get('filter')}]")
        # cb_cond 은 참고만
    else:
        # V4<4 는 기존 cb_cond 로 판단
        if not cb_check.get('passed', False):
            self._log(f"⛔ 차트 조건 미통과: {name} ({cb_check.get('reason', '')})")
            continue
```

### 4.3 포지션 사이징 (가격 필터 반영)

```python
def _get_per_stock_amount_v4(self, investment_type, code, v4_result):
    """V4 가격 필터에 따른 포지션 사이징 조정"""
    base = self._get_per_stock_amount(investment_type, code=code)
    if not v4_result:
        return base
    filter_type = v4_result.get('v4_price_filter', 'NORMAL')
    if filter_type == 'PRIORITY':
        return int(base * 1.2)   # 황금 조합: 20% 추가
    if filter_type == 'SKIP':
        return 0                 # 함정 조합: 0 (차단)
    return base                  # NORMAL
```

### 4.4 레짐별 max_positions

```python
def _get_max_positions_v4(self):
    """시장 레짐에 따른 max_positions 조정"""
    base = self.config.get('max_stocks', 30)
    regime = self._get_current_regime()  # 기존 또는 신규 헬퍼
    if regime == 'BEAR':
        return base // 2     # BEAR: 절반 (15)
    return base              # BULL/SIDEWAYS: 표준 (30)
```

---

## 5. Phase 3C — 장기 정리 (1개월 후)

Phase 3B 안정 동작 확인 시:
- `_check_cb_conditions` 을 V4 로 완전 교체 (레거시 cb_cond1/2/3 제거)
- `predict()` (old) 를 deprecated 처리 → 모든 호출 `predict_v4()` 로 마이그레이션
- `V4_PATCH_DESIGN_v2.md` §6 (Stage 4 마이그레이션) 실행

---

## 6. 적용 체크리스트

### Phase 3A (즉시 적용 가능)
- [ ] Stage 1+2 완료 확인 (`closing_bet_unified.predict_v4` 존재)
- [ ] `trading_system.db` 에 `v4_observations` 테이블 생성
- [ ] `auto_trader.py` L1548~1558 에 §3.2 코드 30줄 삽입
- [ ] `auto_trader.py` 말미에 §3.3 헬퍼 2개 추가
- [ ] `py_compile` 구문 검증
- [ ] `pre_commit_check.py` 13/13 통과
- [ ] 1일 운영 후 `v4_observations` 테이블 row count 확인
- [ ] 1주일 후 v4_score==4 발생 빈도와 기존 cb_cond 통과 건수 비교

### Phase 3B (1~2주 후)
- [ ] v4_observations 실제 갭 집계 (§3.5 쿼리)
- [ ] V4=4 + PRIORITY/NORMAL 실전 실적 설계서 예상 대비 확인
- [ ] 기준 달성 시 §4 게이트 승격 적용
- [ ] Circuit Breaker 연동 확인

### Phase 3C (1개월 후)
- [ ] legacy cb_cond 제거 여부 결정
- [ ] 완전 마이그레이션 진행

---

## 7. 회귀 위험 평가

| 위험 카테고리 | Phase 3A | Phase 3B | Phase 3C |
|--------------|---------|---------|---------|
| 기존 매수 로직 | **0** | 낮음 | 중간 |
| 기존 매도 로직 | **0** | **0** | **0** |
| 포지션 한도 | **0** | 낮음 | 낮음 |
| CB 작동 | **0** | **0** | **0** |
| DB 쓰기 | 매우 낮음 | 매우 낮음 | 매우 낮음 |
| 장애 시 복구성 | 즉시 | 즉시 (rollback 가능) | 신중 |

**Phase 3A 는 순수 관찰 모드 — 회귀 위험 0**.

---

## 8. Seoner 결정 필요 (Stage 3 추가)

1. **Phase 3A 즉시 적용?** (권고: 예 — 위험 0, 가치 높음)
2. **DB 테이블 위치**: `trading_system.db` vs 신규 `v4_observations.db` (권고: trading_system.db)
3. **v4_observations 보존 기간**: 영구 vs 90일 롤링 (권고: 영구 — 백테스트 재활용)
4. **Phase 3B 승격 기준**: §4.1 기준 엄격 vs 완화 (권고: 엄격)

---

## 9. 미해결 사항

### 9.1 실시간 OHLCV 조회 부하
- 종가 매수 직전 50~100종목 각각 70일 OHLCV 조회 필요
- `_analyze_top_targets_for_today` 와 중복 가능성 → 기존 분석 결과 재사용 검토

### 9.2 V4 score==4 발생 빈도
- 백테스트 기준 약 6건/30일 (평균)
- 실전 최근 30일 평균 5건/일 — 강세장 효과
- `max_stocks=5` 와 충돌 가능성 (종가배팅 전용 max 별도 설정 검토)

### 9.3 auto_trader GapUpPredictor 인스턴스 관리
- 매수 체크마다 재생성 vs 싱글톤 — 메모리/성능 영향 검토

---

## 10. 요약

| Phase | 변경량 | 회귀 위험 | 즉시 가능? |
|-------|------|---------|----------|
| 3A | +60줄, DB 1 테이블 | **0** | ✅ 즉시 |
| 3B | +40줄, 로직 분기 변경 | 낮음 | 1~2주 검증 후 |
| 3C | cb_cond 제거 | 중간 | 1개월 후 |

**권고 진행 순서**: Seoner §9 답변 → Stage 1+2 패치 → Phase 3A 즉시 → 2주 관찰 → Phase 3B → 1개월 후 3C.
