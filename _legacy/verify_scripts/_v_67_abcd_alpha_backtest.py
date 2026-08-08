"""_v_67_abcd_alpha_backtest.py — ABCD B×α 진입 차단 임계값의 레짐별 최적 실측

목적:
  auto_trader.py 의 ABCD 진입 로직에서 "B×0.95 이상이면 진입 차단" 임계값을
  레짐별로 차등 적용할 경우 최적 α 값을 데이터로 결정.

방법:
  1. 2024-01~2026-04 기간 전체에서
  2. 매일 각 종목에 대해 auto_trader 의 _find_abcd_simple 로직 재현해서 A/B/C 탐지
  3. 당시 주가를 B×α 비교 (α = 0.90, 0.92, 0.95, 0.97, 0.98, 1.00, 1.02)
  4. "α 통과" 종목을 T0 종가 매수 → T+3 종가 매도 가정
  5. 수수료+슬리피지 0.65% 차감
  6. 레짐 × α 그리드 집계

결과 포맷:
  레짐 | α=0.90 | 0.92 | 0.95 | 0.97 | 0.98 | 1.00 | 1.02
  BULL | 평균수익/승률/N 건
  SIDEWAYS | ...
  BEAR | ...
"""
import sqlite3
import numpy as np
from datetime import datetime
from collections import defaultdict

OHLCV_DB = r'D:\StockAnalyst\ohlcv_long.db'
REGIME_DB = r'D:\StockAnalyst\trading_system.db'
COST_PCT = 0.65  # 왕복 수수료+세금+슬리피지 %
HOLDING_DAYS = 3  # T+3 매도
ALPHAS = [0.90, 0.92, 0.95, 0.97, 0.98, 1.00, 1.02]


def find_abcd_simple(high, low, close):
    """auto_trader._find_abcd_simple 재현 (완전 일치)"""
    n = len(close)
    if n < 20:
        return None
    
    lookback = min(60, n)
    strength = 3
    swing_highs = []
    swing_lows = []
    
    for i in range(strength, lookback - strength):
        idx = n - lookback + i
        if all(high[idx] >= high[idx-j] for j in range(1, strength+1)) and \
           all(high[idx] >= high[idx+j] for j in range(1, strength+1)):
            swing_highs.append((idx, high[idx]))
        if all(low[idx] <= low[idx-j] for j in range(1, strength+1)) and \
           all(low[idx] <= low[idx+j] for j in range(1, strength+1)):
            swing_lows.append((idx, low[idx]))
    
    if len(swing_highs) < 1 or len(swing_lows) < 2:
        return None
    
    swing_lows.sort(key=lambda x: x[0])
    swing_highs.sort(key=lambda x: x[0])
    
    for b_idx, b_price in reversed(swing_highs):
        a_cands = [(i, p) for i, p in swing_lows if i < b_idx]
        if not a_cands:
            continue
        a_idx, a_price = max(a_cands, key=lambda x: x[0])
        if a_price >= b_price:
            continue
        c_cands = [(i, p) for i, p in swing_lows if i > b_idx]
        if not c_cands:
            continue
        c_idx, c_price = min(c_cands, key=lambda x: x[0])
        if c_price <= a_price or c_price >= b_price:
            continue
        ab_range = b_price - a_price
        bc_retrace = (b_price - c_price) / ab_range if ab_range > 0 else 0
        if 0.382 <= bc_retrace <= 0.786:
            return {'a': float(a_price), 'b': float(b_price), 'c': float(c_price),
                    'a_idx': a_idx, 'b_idx': b_idx, 'c_idx': c_idx}
    return None


def load_regimes():
    """market_condition_history 로드"""
    conn = sqlite3.connect(REGIME_DB)
    rows = conn.execute(
        "SELECT date, market_condition FROM market_condition_history "
        "WHERE market_condition IN ('bull', 'sideways', 'bear')"
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def load_ohlcv_by_code():
    """종목별 OHLCV 로드 (2023~2026 범위, 유동성 필터 포함)"""
    conn = sqlite3.connect(OHLCV_DB)
    # 성능을 위해 최근 3년만
    rows = conn.execute(
        "SELECT code, date, open, high, low, close, volume "
        "FROM daily_ohlcv_long "
        "WHERE date >= '20230101' AND date <= '20260417' "
        "  AND substr(code, -1) = '0' "  # 보통주만
        "ORDER BY code, date"
    ).fetchall()
    conn.close()
    
    by_code = defaultdict(list)
    for code, date, o, h, l, c, v in rows:
        by_code[code].append((date, o, h, l, c, v))
    
    # 각 종목 numpy 배열로 변환
    data = {}
    for code, lst in by_code.items():
        if len(lst) < 80:
            continue
        arr = np.array([[x[1], x[2], x[3], x[4], x[5]] for x in lst], dtype=np.float64)
        dates = [x[0] for x in lst]
        data[code] = {'dates': dates, 'arr': arr}
    return data


def run_backtest():
    print('[1/4] 레짐 + OHLCV 로드...')
    regimes = load_regimes()
    print(f'  레짐: {len(regimes)}일')
    
    import time; t0 = time.time()
    ohlcv = load_ohlcv_by_code()
    print(f'  OHLCV: {len(ohlcv)}종목 ({time.time()-t0:.1f}초)')
    
    # α × 레짐 → 수익률 리스트
    results = {a: {'bull': [], 'sideways': [], 'bear': []} for a in ALPHAS}
    total_signals = 0
    valid_signals = 0
    
    # 거래대금 필터 (유동성)
    MIN_TV = 1_000_000_000  # 10억원 이상
    MIN_PRICE = 500
    
    print(f'\n[2/4] 각 종목 × 매일 ABCD 탐지 + α 검증...')
    t0 = time.time()
    
    for ci, (code, d) in enumerate(ohlcv.items()):
        dates = d['dates']; arr = d['arr']
        o, h, l, c, v = arr[:,0], arr[:,1], arr[:,2], arr[:,3], arr[:,4]
        n = len(dates)
        
        # T0 인덱스를 70 ~ n-HOLDING_DAYS-1 로
        for t_idx in range(70, n - HOLDING_DAYS - 1):
            date_t = dates[t_idx]
            if date_t not in regimes:
                continue
            regime = regimes[date_t]
            
            # 유동성 필터
            close_t = c[t_idx]
            if close_t < MIN_PRICE:
                continue
            if close_t * v[t_idx] < MIN_TV:
                continue
            
            # 과거 60일 OHLCV 로 ABCD 탐지
            sub_h = h[:t_idx+1][-60:]
            sub_l = l[:t_idx+1][-60:]
            sub_c = c[:t_idx+1][-60:]
            pattern = find_abcd_simple(sub_h, sub_l, sub_c)
            if not pattern:
                continue
            
            total_signals += 1
            b_price = pattern['b']
            c_price = pattern['c']
            
            # C점 근처 반등 조건: 현재 > C
            if close_t <= c_price:
                continue
            
            valid_signals += 1
            
            # T+3 종가로 매도
            t_exit = t_idx + HOLDING_DAYS
            if t_exit >= n:
                continue
            exit_close = c[t_exit]
            
            # 수익률 (수수료 차감)
            ret_pct = (exit_close / close_t - 1) * 100 - COST_PCT
            
            # 각 α 별로 "통과/차단" 판정
            for alpha in ALPHAS:
                if close_t < b_price * alpha:
                    # α 통과 = 매수 허용
                    results[alpha][regime].append(ret_pct)
        
        if (ci + 1) % 500 == 0:
            print(f'  진행 {ci+1}/{len(ohlcv)} ({time.time()-t0:.1f}초)')
    
    print(f'  완료: {time.time()-t0:.1f}초')
    print(f'  ABCD 탐지 {total_signals}건 중 C구간반등 조건 {valid_signals}건')
    
    return results


def summarize(results):
    print('\n' + '=' * 110)
    print('[3/4] 레짐 × α 그리드 결과 (T+3 매도, 수수료 0.65% 차감)')
    print('=' * 110)
    
    # 헤더
    header = f'{"레짐":<10}'
    for a in ALPHAS:
        header += f' | α={a:.2f}'.ljust(12)
    print(header)
    print('-' * 110)
    
    for regime_name in ['bull', 'sideways', 'bear']:
        row = f'{regime_name:<10}'
        for a in ALPHAS:
            rets = results[a][regime_name]
            if len(rets) == 0:
                row += ' | ' + 'N=0'.ljust(10)
                continue
            arr = np.array(rets)
            mean = arr.mean()
            win = (arr > 0).mean() * 100
            n = len(arr)
            row += f' | {mean:+.2f}% W{win:.0f}% N={n}'.ljust(12)
        print(row)
    
    # 개별 레짐 상세 (Calmar/Sharpe)
    print('\n' + '=' * 110)
    print('[4/4] 레짐별 α 최적값 (Sharpe 기준)')
    print('=' * 110)
    
    for regime_name in ['bull', 'sideways', 'bear']:
        print(f'\n{regime_name.upper()}:')
        print(f'  {"α":<8} {"N":<6} {"평균":<8} {"승률":<6} {"표준":<8} {"Sharpe":<7} {"MDD":<7}')
        print('  ' + '-' * 60)
        for a in ALPHAS:
            rets = results[a][regime_name]
            if len(rets) < 10:
                print(f'  {a:<8.2f} {len(rets):<6} (샘플 부족)')
                continue
            arr = np.array(rets)
            mean = arr.mean()
            std = arr.std()
            sharpe = mean/std if std > 0 else 0
            win = (arr > 0).mean() * 100
            # MDD: 누적수익 drawdown
            cum = (1 + arr/100).cumprod()
            peak = np.maximum.accumulate(cum)
            dd = (cum - peak) / peak
            mdd = dd.min() * 100
            print(f'  {a:<8.2f} {len(arr):<6} {mean:+.3f}% {win:<5.0f}% {std:<7.2f} {sharpe:<7.3f} {mdd:<+6.1f}%')


if __name__ == '__main__':
    print('=' * 110)
    print('ABCD B×α 임계값 레짐별 최적 백테스트')
    print(f'기간: 2024-01 ~ 2026-04, 보유: T+{HOLDING_DAYS}일, 비용: {COST_PCT}%')
    print('=' * 110)
    results = run_backtest()
    summarize(results)
    print('\n완료.')
