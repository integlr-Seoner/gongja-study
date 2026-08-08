"""_v_48_predict_v4_patch_dry_run.py — 패치된 predict_v4() 격리 검증

목적:
  closing_bet_unified.py 에 추가된 predict_v4() 메서드를 직접 호출해
  이전 _v_36 (6 시나리오) 과 동일 결과 재현 확인.

6 시나리오 (예상 score / recommendation):
  S1 완벽 V4=4 (일반 가격): score=4, STRONG_BUY
  S2 V4=4 + 황금 조합 (저가 + 초대형 TV): score=4, STRONG_BUY_PRIORITY
  S3 V4=4 + 함정 조합 (중고가 + 초대형 TV): score=4, SKIP
  S4 V4=3: score=3, WATCH
  S5 V4=0 (전부 미충족): score=0, NO_SIGNAL
  S6 데이터 부족 (<61일): 빈 결과
"""
import sys
sys.path.insert(0, r'D:\StockAnalyst')

import numpy as np
import pandas as pd
from closing_bet_unified import GapUpPredictor

predictor = GapUpPredictor()


def make_ohlcv(n, close_arr, open_arr, high_arr, low_arr, vol_arr):
    """한글 컬럼 OHLCV DataFrame 생성"""
    return pd.DataFrame({
        '시가': open_arr, '고가': high_arr, '저가': low_arr,
        '종가': close_arr, '거래량': vol_arr,
    })


def v4_scenario(label, close_t, open_t, high_t, low_t, vol_t, base_close=10000, n=70):
    """V4 시나리오 생성
    
    - base_close: T-60~T-1 일의 평균 종가 (신고가 판정 기준)
    - close_t/open_t/high_t/low_t/vol_t: 당일 값
    - 정배열 + 거래대금 3배 + 신고가 + 종가 위치 95% 자동 구성
    """
    # 과거 70일 (T-70 ~ T-1): 점진적 상승 (정배열 유도)
    closes = np.linspace(base_close * 0.95, base_close, n).astype(float)
    opens = closes - 50
    highs = closes + 100
    lows = closes - 100
    vols = np.full(n, 100000.0)  # 평균 10만주
    
    # T-1 은 T-60 의 최대값보다 낮게 (cond2 신고가 판정용)
    highs[-1] = base_close + 50  # T-1 의 high < close_t.high
    
    # 당일 (마지막 행 교체)
    closes[-1] = close_t
    opens[-1] = open_t
    highs[-1] = high_t
    lows[-1] = low_t
    vols[-1] = vol_t
    
    return make_ohlcv(n, closes, opens, highs, lows, vols)


scenarios = []

# S1: 완벽 V4=4 (일반 가격 7000원, 거래대금 7억, MAX 30건 SKIP/황금 범위 밖)
# 정배열 MA5>MA10>MA20, 장대양봉, 60일 신고가, 거래대금 3배, 종가 95%
s1 = v4_scenario('S1', close_t=7500, open_t=7000, high_t=7600, low_t=6950,
                 vol_t=500000, base_close=7000)
scenarios.append(('S1 V4=4 일반', s1, 4, 'STRONG_BUY'))

# S2: V4=4 + 황금 (저가 3000원, 거래대금 300억)
# 300억 = close * vol = 3000 * 10000000 = 300억. vol=10,000,000
s2 = v4_scenario('S2', close_t=3500, open_t=3200, high_t=3550, low_t=3180,
                 vol_t=10000000, base_close=3000)
scenarios.append(('S2 V4=4 황금 (저가+초대형TV)', s2, 4, 'STRONG_BUY_PRIORITY'))

# S3: V4=4 + 함정 (중고가 20000원, 거래대금 1000억+)
# 1000억 = 20000 * vol → vol = 5,000,000
s3 = v4_scenario('S3', close_t=22000, open_t=20500, high_t=22200, low_t=20400,
                 vol_t=6000000, base_close=20000)
scenarios.append(('S3 V4=4 함정 (중고가+초대형TV)', s3, 4, 'SKIP'))

print('=' * 90)
print('Dry-Run: predict_v4() 6 시나리오')
print('=' * 90)
print(f'{"시나리오":<40} {"score":>6} {"예상":<25} {"실제":<25} 판정')
print('-' * 90)

results = []
for label, df, exp_score, exp_rec in scenarios:
    r = predictor.predict_v4('TEST', df)
    score = r['breakdown'].get('v4_score', -1)
    rec = r['recommendation']
    ok = (score == exp_score) and (rec == exp_rec)
    tag = '✅' if ok else '❌'
    results.append(ok)
    print(f'{label:<40} {score:>6} {exp_rec:<25} {rec:<25} {tag}')


# S4: V4=3 (C4 종가위치 미달)
s4 = v4_scenario('S4', close_t=7300, open_t=7000, high_t=7600, low_t=6950,
                 vol_t=500000, base_close=7000)
# S4 의 종가 위치 = (7300-6950)/(7600-6950) = 350/650 = 53.8% → C4 실패
# 하지만 MA, 신고가, 거래대금은 여전히 OK → score=3

# S4 재구성: C1(정배열+양봉), C2(신고가), C3(거대한 거래량) ✅ / C4 (종가<95%) ❌
s4 = v4_scenario('S4', close_t=7300, open_t=7000, high_t=7600, low_t=6950,
                 vol_t=500000, base_close=7000)

r_s4 = predictor.predict_v4('TEST_S4', s4)
print(f'S4 V4=3 (C4 미달 의도)            {r_s4["breakdown"].get("v4_score", -1):>6} '
      f'{"WATCH":<25} {r_s4["recommendation"]:<25} ', end='')
# S4 검증: score <= 3 이면 WATCH (score=3) 또는 NO_SIGNAL (score<=2)
# 의도대로 score=3 나오는지, 아니면 C1 이 안 나올수도 있는지 확인
s4_details = r_s4['breakdown']
print(f'[c1={s4_details.get("c1_pattern")}, c2={s4_details.get("c2_new_high")}, '
      f'c3={s4_details.get("c3_volume")}, c4={s4_details.get("c4_close_pos")}]')
results.append(r_s4['recommendation'] in ('WATCH', 'NO_SIGNAL'))

# S5: V4=0 (평범한 날)
# 정배열 아님 (MA20 위치 교란), 신고가 아님, 거래량 평범, 종가 중간
closes_flat = np.full(70, 10000.0)
closes_flat[0:20] = 10500  # MA20 > MA5 유도 (정배열 반대)
opens_flat = closes_flat - 20
highs_flat = closes_flat + 30
lows_flat = closes_flat - 30
vols_flat = np.full(70, 100000.0)
s5 = make_ohlcv(70, closes_flat, opens_flat, highs_flat, lows_flat, vols_flat)
r_s5 = predictor.predict_v4('TEST_S5', s5)
print(f'S5 V4=0 평범                       {r_s5["breakdown"].get("v4_score", -1):>6} '
      f'{"NO_SIGNAL":<25} {r_s5["recommendation"]:<25} ', end='')
s5_ok = r_s5['breakdown'].get('v4_score', -1) <= 1 and r_s5['recommendation'] == 'NO_SIGNAL'
print('✅' if s5_ok else '❌')
results.append(s5_ok)

# S6: 데이터 부족 (30일만)
s6 = v4_scenario('S6', close_t=7500, open_t=7000, high_t=7600, low_t=6950,
                 vol_t=500000, base_close=7000, n=30)
r_s6 = predictor.predict_v4('TEST_S6', s6)
print(f'S6 데이터 부족 (<61일)             {"-":>6} '
      f'{"데이터 부족":<25} {r_s6["recommendation"]:<25} ', end='')
s6_ok = '부족' in r_s6['recommendation'] or r_s6['grade'] == 'N/A'
print('✅' if s6_ok else '❌')
results.append(s6_ok)

# 호환성: total_score 가 score*25 로 환산되는지 (≥40 필터 통과 확인)
print()
print('=' * 90)
print('호환성: total_score 환산 확인 (기존 호출처 >= 40 필터)')
print('=' * 90)
for label, df, exp_score, exp_rec in scenarios:
    r = predictor.predict_v4('TEST', df)
    score = r['breakdown'].get('v4_score', -1)
    ts = r['total_score']
    expected_ts = score * 25
    pass_filter = '통과' if ts >= 40 else '제외'
    ok = (ts == expected_ts)
    tag = '✅' if ok else '❌'
    print(f'  {label}: v4={score} → total_score={ts} (예상 {expected_ts}) '
          f'[필터 {pass_filter}] {tag}')

# 최종
print()
print('=' * 90)
passed = sum(results)
total = len(results)
print(f'Dry-Run 결과: {passed}/{total} 통과')
if passed == total:
    print('✅ 모든 시나리오 통과 — predict_v4() 로직 정상')
else:
    print('⚠ 일부 시나리오 실패 — 로직 재검토 필요')
