"""_v_49_dry_run_diagnostic.py — _v_48 실패 원인 진단"""
import sys
sys.path.insert(0, r'D:\StockAnalyst')
import numpy as np
import pandas as pd

# S1 재현
n = 70
base_close = 7000
closes = np.linspace(base_close * 0.95, base_close, n).astype(float)
opens = closes - 50
highs = closes + 100
lows = closes - 100
vols = np.full(n, 100000.0)
highs[-1] = base_close + 50

# 당일
closes[-1] = 7500
opens[-1] = 7000
highs[-1] = 7600
lows[-1] = 6950
vols[-1] = 500000

# MA 계산
close_s = pd.Series(closes)
ma5 = close_s.rolling(5).mean().iloc[-1]
ma10 = close_s.rolling(10).mean().iloc[-1]
ma20 = close_s.rolling(20).mean().iloc[-1]
print(f'S1 분석:')
print(f'  MA5  = {ma5:.2f}')
print(f'  MA10 = {ma10:.2f}')
print(f'  MA20 = {ma20:.2f}')
print(f'  정배열 (MA5>MA10>MA20): {ma5 > ma10 > ma20}')

# C1 체크
body = closes[-1] - opens[-1]
rng = highs[-1] - lows[-1]
print(f'  body={body}, rng={rng}, body/rng={body/rng:.3f} (>0.6 필요)')

# C2 체크
prev60_max = pd.Series(highs).iloc[-61:-1].max()
print(f'  prev60 max high = {prev60_max}, today high = {highs[-1]}')
print(f'  C2 신고가: {highs[-1] > prev60_max}')

# C3 체크
tv = close_s.iloc[-21:-1] * pd.Series(vols).iloc[-21:-1]
tv_avg = tv.mean()
today_tv = closes[-1] * vols[-1]
print(f'  C3: today_tv={today_tv:.0f}, avg20={tv_avg:.0f}, ratio={today_tv/tv_avg:.2f} (>=3.0 필요)')

# C4 체크
c4_pos = (closes[-1] - lows[-1]) / rng
print(f'  C4 종가 위치: {c4_pos:.3f} (>=0.95 필요)')
