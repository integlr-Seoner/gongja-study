"""_v_28_predict_v4_dry_run.py — V4 패치 설계서 검증 (Dry-Run)

목적:
  V4_PATCH_DESIGN.md §3.1, §3.2 의 코드를 closing_bet_unified.py 에
  실제 패치하기 전에 격리 환경에서 import + 호출 가능성 + 결과 정합성 검증.

검증 항목:
  ① 헬퍼 메서드 5개 컴파일 가능 (구문 OK)
  ② 더미 OHLCV DataFrame 으로 predict_v4() 정상 반환
  ③ score==4/3/0 케이스에서 등급/총점 환산 정확
  ④ 기존 predict() 호환 키 5개 모두 포함 (total_score/grade/expected_gap/breakdown/recommendation)
  ⑤ ohlcv 데이터 부족 (20행 미만) 시 _empty_result_v4 정상 반환

원칙:
  closing_bet_unified.py 무수정 (③Surgical Changes)
  격리된 클래스로 패치 코드 사전 시험
"""
import pandas as pd
import numpy as np


# ============================================================================
# 패치 설계서의 코드를 격리된 형태로 정의 (closing_bet_unified.py 수정 X)
# ============================================================================
class GapUpPredictorV4Patch:
    """V4_PATCH_DESIGN.md §3 Stage 1+2 의 코드 그대로"""

    def predict_v4(self, code, ohlcv):
        if len(ohlcv) < 60:
            return self._empty_result_v4(code, "데이터 부족")
        cond1 = self._is_align_and_big_candle(ohlcv)
        cond2 = self._is_60day_new_high(ohlcv)
        cond3 = self._get_volume_value_ratio(ohlcv) >= 3.0
        cond4 = self._get_close_position(ohlcv) >= 0.95
        v4_score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
        if v4_score == 4:
            grade = "STRONG_BUY"; gap = "3-5%+"; legacy_grade = "HIGH"
            rec = "적극 매수 (4조건 모두 충족, realized +3.044%)"
        elif v4_score == 3:
            grade = "BUY"; gap = "0-1%"; legacy_grade = "MEDIUM"
            rec = "보조 매수 (realized +0.370%)"
        else:
            grade = "WATCH"; gap = "불확실"
            legacy_grade = "LOW" if v4_score == 2 else "VERY_LOW"
            rec = "관망 (조건 부족)"
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
            'total_score': v4_score * 25,
            'grade': legacy_grade,
            'breakdown': {
                'v4_chart': (int(cond1) + int(cond2)) * 25,
                'v4_volume': int(cond3) * 25,
                'v4_position': int(cond4) * 25,
                'news': 0,
            },
        }

    def _is_align_and_big_candle(self, ohlcv):
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

    def _is_60day_new_high(self, ohlcv):
        h = ohlcv['High'].values
        if len(h) < 61:
            return False
        return h[-1] > h[-61:-1].max()

    def _get_volume_value_ratio(self, ohlcv):
        c = ohlcv['Close'].values
        v = ohlcv['Volume'].values
        if len(c) < 21:
            return 0.0
        today_tv = c[-1] * v[-1]
        avg20_tv = (c[-21:-1] * v[-21:-1]).mean()
        return today_tv / avg20_tv if avg20_tv > 0 else 0.0

    def _get_close_position(self, ohlcv):
        h = ohlcv['High'].values[-1]
        l = ohlcv['Low'].values[-1]
        c = ohlcv['Close'].values[-1]
        rng = h - l
        return (c - l) / rng if rng > 0 else 0.0

    def _empty_result_v4(self, code, reason):
        return {
            'code': code, 'v4_score': 0, 'v4_grade': 'WATCH',
            'v4_conditions': {}, 'expected_gap': '불확실',
            'recommendation': reason,
            'total_score': 0, 'grade': 'VERY_LOW', 'breakdown': {},
        }


# ============================================================================
# 검증 케이스
# ============================================================================
def make_ohlcv(scenario):
    """시나리오별 합성 OHLCV (60+ 행)
    
    주의: V4의 close_position >= 0.95 는 매우 엄격. 
    합성 시 high - low 폭의 95%↑ 위치에 close 가 와야 함.
    """
    n = 70
    rng = np.random.default_rng(42)
    if scenario == 'score_4':
        # 모든 4조건 충족: 정배열 강한 상승 + 신고가 + 거래대금 폭증 + 종가 95%↑
        close = np.linspace(8000, 12000, n) + rng.normal(0, 50, n)
        # 마지막 봉: 시가에서 거의 고가까지 강하게 상승, 종가 = 고가 (close_pos = 1.0)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005      # 시가 약간 위
        close[-1] = prev_close * 1.10         # 종가 +10%
        high = close * 1.02
        high[-1] = close[-1]                 # 고가 = 종가 (close_pos = 1.0 → 95%↑ 충족)
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998         # 저가 = 시가 살짝 아래
        vol = np.full(n, 100_000)
        vol[-1] = 500_000                    # 5배 폭증
    elif scenario == 'score_3':
        # 정배열+장대양봉+종가95%↑+신고가 충족, 거래대금만 부족
        # → ①과 동일 close/high/low 구조, 거래량만 1.5배
        close = np.linspace(8000, 12000, n) + rng.normal(0, 50, n)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005
        close[-1] = prev_close * 1.10
        high = close * 1.02
        high[-1] = close[-1]                 # close_pos = 1.0
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998
        vol = np.full(n, 100_000)
        vol[-1] = 150_000                    # 1.5배만 (3배 미달)
    elif scenario == 'score_0':
        # 횡보 + 약한 거래량 + 종가 중간
        close = np.full(n, 10000.0) + rng.normal(0, 50, n)
        open_p = close - 50
        high = close + 100
        low = close - 100
        vol = np.full(n, 100_000)
    elif scenario == 'too_short':
        n = 30  # 60 미만
        close = np.full(n, 10000.0)
        open_p = close.copy()
        high = close * 1.01
        low = close * 0.99
        vol = np.full(n, 100_000)
    return pd.DataFrame({
        'Open': open_p, 'High': high, 'Low': low,
        'Close': close, 'Volume': vol,
    })


def run_test(name, scenario, expected_score, expected_grade):
    df = make_ohlcv(scenario)
    p = GapUpPredictorV4Patch()
    r = p.predict_v4('TEST', df)
    
    print(f'\n--- {name} ---')
    print(f'  v4_score: {r["v4_score"]} (예상 {expected_score})')
    print(f'  v4_grade: {r["v4_grade"]} (예상 {expected_grade})')
    print(f'  legacy total_score: {r["total_score"]}')
    print(f'  legacy grade: {r["grade"]}')
    print(f'  conditions: {r["v4_conditions"]}')
    print(f'  expected_gap: {r["expected_gap"]}')
    
    # 호환성 체크 — 5개 키 존재
    required = ['total_score', 'grade', 'expected_gap', 'breakdown', 'recommendation']
    missing = [k for k in required if k not in r]
    
    score_ok = r['v4_score'] == expected_score
    grade_ok = r['v4_grade'] == expected_grade
    keys_ok = not missing
    
    status = '✅' if (score_ok and grade_ok and keys_ok) else '❌'
    print(f'  → {status} score={"OK" if score_ok else "FAIL"} '
          f'grade={"OK" if grade_ok else "FAIL"} '
          f'keys={"OK" if keys_ok else f"MISS:{missing}"}')
    
    return score_ok and grade_ok and keys_ok


if __name__ == '__main__':
    print('=' * 70)
    print('V4 패치 설계서 Dry-Run 검증')
    print('=' * 70)

    results = []
    results.append(run_test('① 4조건 모두 충족', 'score_4', 4, 'STRONG_BUY'))
    results.append(run_test('② 3조건 충족 (거래대금 부족)', 'score_3', 3, 'BUY'))
    results.append(run_test('③ 0조건 충족 (횡보)', 'score_0', 0, 'WATCH'))
    results.append(run_test('④ 데이터 부족 (n=30)', 'too_short', 0, 'WATCH'))

    print()
    print('=' * 70)
    passed = sum(results)
    print(f'결과: {passed}/{len(results)} 통과')
    print('=' * 70)
    if passed == len(results):
        print('✅ V4 패치 설계서 검증 완료 — closing_bet_unified.py 패치 가능')
    else:
        print('❌ 설계 결함 — 패치 전 수정 필요')
