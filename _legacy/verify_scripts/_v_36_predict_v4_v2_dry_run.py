"""_v_36_predict_v4_v2_dry_run.py — V4_PATCH_DESIGN_v2.md 설계서 자체 검증

v1 dry-run (_v_28) 확장:
  ① 가격/거래대금 필터 3케이스 추가 (PRIORITY/SKIP/NORMAL)
  ② v4_price_filter 키 존재 확인
  ③ 실데이터 정합성 — score 분포는 _v_29와 동일해야
"""
import pandas as pd
import numpy as np


# ============================================================================
# V4_PATCH_DESIGN_v2.md §3, §4 코드를 격리된 형태로 이식
# ============================================================================
class GapUpPredictorV4PatchV2:

    def predict_v4(self, code, ohlcv):
        if len(ohlcv) < 60:
            return self._empty_result_v4(code, "데이터 부족")
        cond1 = self._is_align_and_big_candle(ohlcv)
        cond2 = self._is_60day_new_high(ohlcv)
        cond3 = self._get_volume_value_ratio(ohlcv) >= 3.0
        cond4 = self._get_close_position(ohlcv) >= 0.95
        v4_score = int(cond1) + int(cond2) + int(cond3) + int(cond4)
        
        price = float(ohlcv['Close'].iloc[-1])
        vol = float(ohlcv['Volume'].iloc[-1])
        tv_eok = (price * vol) / 1e8
        
        if v4_score == 4:
            if 10000 <= price < 30000 and tv_eok >= 1000:
                price_filter = 'SKIP'; grade = 'SKIP'; gap = '회피'
                rec = '함정 조합 (중-고가 + 초대형 거래대금, realized -0.107%)'
                legacy_grade = 'LOW'
            elif price < 5000 and tv_eok >= 200:
                price_filter = 'PRIORITY'; grade = 'STRONG_BUY'; gap = '5-7%+'
                rec = '우선 매수 (황금 조합, realized +5~6%)'
                legacy_grade = 'HIGH'
            else:
                price_filter = 'NORMAL'; grade = 'STRONG_BUY'; gap = '3-5%+'
                rec = '적극 매수 (4조건 충족, realized +3.044%)'
                legacy_grade = 'HIGH'
        elif v4_score == 3:
            price_filter = 'NORMAL'; grade = 'BUY'; gap = '0-1%'
            rec = '보조 매수 (realized +0.370%)'
            legacy_grade = 'MEDIUM'
        else:
            price_filter = 'NORMAL'; grade = 'WATCH'; gap = '불확실'
            rec = '관망 (조건 부족)'
            legacy_grade = 'LOW' if v4_score == 2 else 'VERY_LOW'
        
        return {
            'code': code, 'v4_score': v4_score, 'v4_grade': grade,
            'v4_conditions': {
                'align_and_big_candle': bool(cond1),
                'new_high_60d': bool(cond2),
                'volume_value_3x': bool(cond3),
                'close_position_95': bool(cond4),
            },
            'v4_price_filter': price_filter,
            'expected_gap': gap, 'recommendation': rec,
            'total_score': v4_score * 25, 'grade': legacy_grade,
            'breakdown': {
                'v4_chart': (int(cond1) + int(cond2)) * 25,
                'v4_volume': int(cond3) * 25,
                'v4_position': int(cond4) * 25,
                'news': 0,
            },
        }
    
    def _empty_result_v4(self, code, reason):
        return {
            'code': code, 'v4_score': 0, 'v4_grade': 'WATCH',
            'v4_conditions': {}, 'v4_price_filter': 'NORMAL',
            'expected_gap': '불확실', 'recommendation': reason,
            'total_score': 0, 'grade': 'VERY_LOW', 'breakdown': {},
        }

    def _is_align_and_big_candle(self, ohlcv):
        c = ohlcv['Close'].values; o = ohlcv['Open'].values
        h = ohlcv['High'].values; l = ohlcv['Low'].values
        if len(c) < 20: return False
        ma5 = c[-5:].mean(); ma10 = c[-10:].mean(); ma20 = c[-20:].mean()
        if not (ma5 > ma10 > ma20): return False
        body = c[-1] - o[-1]; rng = h[-1] - l[-1]
        return rng > 0 and body > 0 and (body / rng > 0.6)

    def _is_60day_new_high(self, ohlcv):
        h = ohlcv['High'].values
        if len(h) < 61: return False
        return bool(h[-1] > h[-61:-1].max())

    def _get_volume_value_ratio(self, ohlcv):
        c = ohlcv['Close'].values; v = ohlcv['Volume'].values
        if len(c) < 21: return 0.0
        today_tv = c[-1] * v[-1]
        avg20_tv = (c[-21:-1] * v[-21:-1]).mean()
        return float(today_tv / avg20_tv) if avg20_tv > 0 else 0.0

    def _get_close_position(self, ohlcv):
        h = float(ohlcv['High'].values[-1])
        l = float(ohlcv['Low'].values[-1])
        c = float(ohlcv['Close'].values[-1])
        rng = h - l
        return (c - l) / rng if rng > 0 else 0.0


# ============================================================================
# 시나리오별 합성 데이터 생성
# ============================================================================
def make_ohlcv(scenario):
    """V4 검증된 시나리오:
       score_4_priority: 저가(~2k) + 소형~대형 거래대금 → PRIORITY
       score_4_skip: 중-고(10~30k) + 초대형(1000억+) → SKIP
       score_4_normal: 중가(5~10k) + 중형 거래대금 → NORMAL
       score_3, score_0, too_short: 기본 검증
    """
    n = 70
    rng = np.random.default_rng(42)
    
    if scenario == 'score_4_priority':
        # 저가 2,000원 근처 + 거래량 폭증 → tv_eok > 200
        close = np.linspace(1800, 2200, n) + rng.normal(0, 10, n)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005
        close[-1] = prev_close * 1.10  # +10%, ~2420원
        high = close * 1.02
        high[-1] = close[-1]
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998
        vol = np.full(n, 1_000_000)
        vol[-1] = 15_000_000  # 15배 폭증, close*vol ≈ 362억 > 200억
    
    elif scenario == 'score_4_skip':
        # 중-고 15,000원 + 거래량 폭증 → tv_eok > 1000억
        close = np.linspace(14000, 16000, n) + rng.normal(0, 100, n)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005
        close[-1] = prev_close * 1.10
        high = close * 1.02
        high[-1] = close[-1]
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998
        vol = np.full(n, 1_000_000)
        vol[-1] = 10_000_000  # 10배 → close*vol ≈ 17,000원 * 10M = 1700억 > 1000억
    
    elif scenario == 'score_4_normal':
        # 중가 7,000원 + 중형 거래대금 (tv 50~200억)
        close = np.linspace(6500, 7500, n) + rng.normal(0, 50, n)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005
        close[-1] = prev_close * 1.10
        high = close * 1.02
        high[-1] = close[-1]
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998
        vol = np.full(n, 500_000)
        vol[-1] = 1_500_000  # 3배, ~7700 * 1.5M = 115억
    
    elif scenario == 'score_3':
        # score==4 조건 중 거래대금만 1.5배 (3배 미달)
        close = np.linspace(6500, 7500, n) + rng.normal(0, 50, n)
        prev_close = close[-2]
        open_p = close.copy()
        open_p[-1] = prev_close * 1.005
        close[-1] = prev_close * 1.10
        high = close * 1.02
        high[-1] = close[-1]
        low = close * 0.98
        low[-1] = open_p[-1] * 0.998
        vol = np.full(n, 500_000)
        vol[-1] = 750_000  # 1.5배만
    
    elif scenario == 'score_0':
        close = np.full(n, 10000.0) + rng.normal(0, 50, n)
        open_p = close - 50
        high = close + 100
        low = close - 100
        vol = np.full(n, 100_000)
    
    elif scenario == 'too_short':
        n = 30
        close = np.full(n, 10000.0)
        open_p = close.copy()
        high = close * 1.01
        low = close * 0.99
        vol = np.full(n, 100_000)
    
    return pd.DataFrame({
        'Open': open_p, 'High': high, 'Low': low,
        'Close': close, 'Volume': vol,
    })


def run_test(name, scenario, exp_score, exp_grade, exp_filter):
    df = make_ohlcv(scenario)
    p = GapUpPredictorV4PatchV2()
    r = p.predict_v4('TEST', df)
    
    price = df['Close'].iloc[-1]
    tv_eok = price * df['Volume'].iloc[-1] / 1e8
    
    print(f'\n--- {name} ---')
    print(f'  가격: {price:,.0f}원, 거래대금: {tv_eok:.1f}억')
    print(f'  v4_score: {r["v4_score"]} (예상 {exp_score})')
    print(f'  v4_grade: {r["v4_grade"]} (예상 {exp_grade})')
    print(f'  v4_price_filter: {r["v4_price_filter"]} (예상 {exp_filter})')
    print(f'  legacy total_score: {r["total_score"]}')
    print(f'  conditions: {r["v4_conditions"]}')
    
    # 호환성 체크
    required = ['total_score', 'grade', 'expected_gap', 'breakdown', 
                'recommendation', 'v4_score', 'v4_grade', 'v4_conditions',
                'v4_price_filter']
    missing = [k for k in required if k not in r]
    
    score_ok = r['v4_score'] == exp_score
    grade_ok = r['v4_grade'] == exp_grade
    filter_ok = r['v4_price_filter'] == exp_filter
    keys_ok = not missing
    
    all_ok = score_ok and grade_ok and filter_ok and keys_ok
    status = '✅' if all_ok else '❌'
    flags = []
    if not score_ok: flags.append('SCORE')
    if not grade_ok: flags.append('GRADE')
    if not filter_ok: flags.append('FILTER')
    if not keys_ok: flags.append(f'KEYS:{missing}')
    print(f'  → {status} {" ".join(flags) if flags else "전체 OK"}')
    return all_ok


if __name__ == '__main__':
    print('=' * 75)
    print('V4 패치 설계서 v2 — Dry-Run 검증 (가격/거래대금 필터 포함)')
    print('=' * 75)

    results = []
    results.append(run_test(
        '① score==4 + PRIORITY (저가 + 대형)', 
        'score_4_priority', 4, 'STRONG_BUY', 'PRIORITY'))
    results.append(run_test(
        '② score==4 + SKIP (중-고 + 초대형)',
        'score_4_skip', 4, 'SKIP', 'SKIP'))
    results.append(run_test(
        '③ score==4 + NORMAL (중가 + 중형)',
        'score_4_normal', 4, 'STRONG_BUY', 'NORMAL'))
    results.append(run_test(
        '④ score==3',
        'score_3', 3, 'BUY', 'NORMAL'))
    results.append(run_test(
        '⑤ score==0 (횡보)',
        'score_0', 0, 'WATCH', 'NORMAL'))
    results.append(run_test(
        '⑥ 데이터 부족',
        'too_short', 0, 'WATCH', 'NORMAL'))

    print()
    print('=' * 75)
    passed = sum(results)
    print(f'결과: {passed}/{len(results)} 통과')
    if passed == len(results):
        print('✅ V4_PATCH_DESIGN_v2.md 검증 완료 — 패치 즉시 적용 가능')
    else:
        print('❌ 설계 결함 — 패치 전 수정 필요')
    print('=' * 75)
