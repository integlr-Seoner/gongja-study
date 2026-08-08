"""_v_50_predict_v4_dry_run_fixed.py — 테스트 데이터 수정 후 재검증

_v_48 진단: 테스트 데이터의 종가 위치가 95% 미만 → C4 실패 → score=3
수정: C4 도 충족하도록 close=high (또는 low 를 크게 낮춤) 조정.
"""
import sys
sys.path.insert(0, r'D:\StockAnalyst')

import numpy as np
import pandas as pd
from closing_bet_unified import GapUpPredictor

predictor = GapUpPredictor()


def make_v4_pass(close_t, low_t, high_t, open_t, vol_t, base_close=10000, n=70):
    """V4 4조건 모두 pass 하도록 데이터 생성
    - 정배열 (MA5>MA10>MA20): 과거 상승 추세
    - 장대양봉: body/range > 0.6
    - 60일 신고가: today.high > prev60.max
    - 거래대금 3배: 평균 대비 3배+
    - 종가 95%: (close-low)/(high-low) >= 0.95
    """
    closes = np.linspace(base_close * 0.90, base_close * 0.98, n).astype(float)
    opens = closes - 50
    highs = closes + 50  # 과거 high 를 낮게 유지 (신고가 판정 쉽게)
    lows = closes - 100
    vols = np.full(n, 100000.0)
    
    closes[-1] = close_t
    opens[-1] = open_t
    highs[-1] = high_t
    lows[-1] = low_t
    vols[-1] = vol_t
    return pd.DataFrame({
        '시가': opens, '고가': highs, '저가': lows, '종가': closes, '거래량': vols,
    })


print('=' * 90)
print('Dry-Run (수정): predict_v4() 시나리오 검증')
print('=' * 90)

# S1: 완벽 V4=4 (일반, 7500원)
# close 가 high 에 근접 (95%+)
# body/range = 0.6+, 신고가, 거래대금 3배+, 종가 95%+
# close=7580, open=7000, high=7600, low=6950: (7580-6950)/(7600-6950) = 630/650 = 0.969 ✅
# body = 7580-7000 = 580, rng = 650, ratio = 0.892 ✅
s1 = make_v4_pass(close_t=7580, open_t=7000, high_t=7600, low_t=6950,
                  vol_t=500000, base_close=7000)
r1 = predictor.predict_v4('S1', s1)
ok1 = r1['breakdown']['v4_score'] == 4 and r1['recommendation'] == 'STRONG_BUY'
print(f'S1 완벽 V4=4 (일반 7580원):      score={r1["breakdown"]["v4_score"]}, '
      f'rec={r1["recommendation"]} {"✅" if ok1 else "❌"}')
print(f'   breakdown: c1={r1["breakdown"]["c1_pattern"]}, c2={r1["breakdown"]["c2_new_high"]}, '
      f'c3={r1["breakdown"]["c3_volume"]}, c4={r1["breakdown"]["c4_close_pos"]}')

# S2: V4=4 + 황금 (저가 3500원 + 초대형 TV)
# close=3480, open=3200, high=3500, low=3180
# (3480-3180)/(3500-3180) = 300/320 = 0.9375 → 0.95 미달!
# 개선: close=3495, low=3180, high=3500 → (315)/(320) = 0.984 ✅
s2 = make_v4_pass(close_t=3495, open_t=3200, high_t=3500, low_t=3180,
                  vol_t=10000000, base_close=3000)
r2 = predictor.predict_v4('S2', s2)
ok2 = r2['breakdown']['v4_score'] == 4 and r2['recommendation'] == 'STRONG_BUY_PRIORITY'
print(f'S2 황금 (close=3495, TV 초대형): score={r2["breakdown"]["v4_score"]}, '
      f'rec={r2["recommendation"]} {"✅" if ok2 else "❌"}')

# S3: V4=4 + 함정 (close=21990, high=22000, low=20400, 초대형 TV)
# (21990-20400)/(22000-20400) = 1590/1600 = 0.994 ✅
s3 = make_v4_pass(close_t=21990, open_t=20500, high_t=22000, low_t=20400,
                  vol_t=6000000, base_close=20000)
r3 = predictor.predict_v4('S3', s3)
ok3 = r3['breakdown']['v4_score'] == 4 and r3['recommendation'] == 'SKIP'
print(f'S3 함정 (close=21990, 중고가+초대형TV): score={r3["breakdown"]["v4_score"]}, '
      f'rec={r3["recommendation"]} {"✅" if ok3 else "❌"}')

# S4: V4=3 (C4 의도 미달 — close 가 high 근접하지 않음)
s4 = make_v4_pass(close_t=7300, open_t=7000, high_t=7600, low_t=6950,
                  vol_t=500000, base_close=7000)
r4 = predictor.predict_v4('S4', s4)
ok4 = r4['breakdown']['v4_score'] == 3 and r4['recommendation'] == 'WATCH'
print(f'S4 V4=3 (C4 미달):              score={r4["breakdown"]["v4_score"]}, '
      f'rec={r4["recommendation"]} {"✅" if ok4 else "❌"}')

# S5: V4=0 (평범)
closes = np.full(70, 10000.0)
closes[0:20] = 10500  # 역배열
df5 = pd.DataFrame({
    '시가': closes - 20, '고가': closes + 30, '저가': closes - 30,
    '종가': closes, '거래량': np.full(70, 100000.0),
})
r5 = predictor.predict_v4('S5', df5)
ok5 = r5['breakdown']['v4_score'] <= 1 and r5['recommendation'] == 'NO_SIGNAL'
print(f'S5 V4=0 (평범):                  score={r5["breakdown"]["v4_score"]}, '
      f'rec={r5["recommendation"]} {"✅" if ok5 else "❌"}')

# S6: 데이터 부족
s6 = make_v4_pass(close_t=7580, open_t=7000, high_t=7600, low_t=6950,
                  vol_t=500000, base_close=7000, n=30)
r6 = predictor.predict_v4('S6', s6)
ok6 = '부족' in r6['recommendation']
print(f'S6 데이터 부족 (<61):            grade={r6["grade"]}, '
      f'rec={r6["recommendation"]} {"✅" if ok6 else "❌"}')

# 호환성 재확인
print()
print('=' * 90)
print('호환성: total_score = v4_score * 25 확인')
print('=' * 90)
for label, r in [('S1', r1), ('S2', r2), ('S3', r3), ('S4', r4), ('S5', r5)]:
    score = r['breakdown']['v4_score']
    ts = r['total_score']
    expected = score * 25
    ok = (ts == expected)
    print(f'  {label}: v4={score}, total_score={ts} (예상 {expected}) {"✅" if ok else "❌"}')

# 최종 판정
print()
print('=' * 90)
all_ok = [ok1, ok2, ok3, ok4, ok5, ok6]
passed = sum(all_ok)
print(f'Dry-Run: {passed}/6 통과')
if passed == 6:
    print('✅ 모든 시나리오 통과 — 패치 검증 완료')
else:
    print(f'⚠ {6-passed}개 실패 — 로직 재검토 필요')
    for i, ok in enumerate(all_ok, 1):
        if not ok:
            print(f'  S{i} 실패')
