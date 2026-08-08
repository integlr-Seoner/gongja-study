"""검증: 스팩(SPAC)의 OHLCV 행동 특성 vs 일반 종목
근본: is_excluded_stock에서 스팩을 거르는 이유 실측
  - 스팩은 합병 전까지 2,000원 부근 고정되어 있고 거래량 적음
  - 일반주와 가격 움직임 패턴이 다름
  - 종가배팅 전략이 적용되면 왜곡된 결과 가능성

지표:
  - 평균 가격 분포 (스팩은 대부분 2,000원 부근 고정)
  - 일일 수익률 변동성 (스팩은 합병 시까지 변동 낮음)
  - 거래량 (스팩은 적음)
  - 0% 변동일 비율 (스팩은 변동 없는 날 多)
"""
import sqlite3
import numpy as np
from collections import defaultdict

DB = r'D:\StockAnalyst\ohlcv_long.db'
SRC = r'D:\StockAnalyst\trading_system.db'

conn = sqlite3.connect(DB, timeout=30)
src = sqlite3.connect(SRC, timeout=30)

# 스팩 이름 가진 종목 코드 찾기 (dart_corp_codes에서)
spac_rows = src.execute("""
    SELECT stock_code, corp_name
    FROM dart_corp_codes
    WHERE stock_code IS NOT NULL
      AND (corp_name LIKE '%스팩%' OR corp_name LIKE '%SPAC%'
           OR corp_name LIKE '%기업인수목적%')
""").fetchall()
spac_codes = {c for c, n in spac_rows if c}
print(f'dart_corp_codes에서 스팩 종목: {len(spac_codes)}개')

# 리츠
reit_rows = src.execute("""
    SELECT stock_code, corp_name
    FROM dart_corp_codes
    WHERE stock_code IS NOT NULL
      AND (corp_name LIKE '%리츠%' OR corp_name LIKE '%REIT%'
           OR corp_name LIKE '%인프라%')
""").fetchall()
reit_codes = {c for c, n in reit_rows if c}
print(f'리츠/인프라 종목: {len(reit_codes)}개')

src.close()

# 스팩 중 ohlcv_long.db에 데이터 있는 것만
available_spacs = set()
for code in spac_codes:
    r = conn.execute("SELECT COUNT(*) FROM daily_ohlcv_long WHERE code = ?",
                     (code,)).fetchone()
    if r and r[0] > 50:
        available_spacs.add(code)

available_reits = set()
for code in reit_codes:
    r = conn.execute("SELECT COUNT(*) FROM daily_ohlcv_long WHERE code = ?",
                     (code,)).fetchone()
    if r and r[0] > 50:
        available_reits.add(code)

print(f'\nohlcv_long.db에 데이터 있는:')
print(f'  스팩: {len(available_spacs)}개')
print(f'  리츠/인프라: {len(available_reits)}개')

# 일반 종목 샘플 (스팩/리츠 제외, 코드 0~9 숫자만, 무작위 200개)
all_codes_rows = conn.execute("""
    SELECT DISTINCT code FROM daily_ohlcv_long
    WHERE code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
""").fetchall()
all_codes = {r[0] for r in all_codes_rows}
all_codes -= spac_codes
all_codes -= reit_codes
normal_sample = sorted(all_codes)[:200]  # 결정론적 샘플

print(f'  비교 대상 일반 종목 (sample): {len(normal_sample)}개')


def measure(codes, label):
    """해당 종목군의 OHLCV 특성 측정"""
    prices = []
    vols = []    # 거래량
    rets = []    # 일일 수익률(%)
    zero_change = 0  # 변동 0% 일수
    total_days = 0
    under_3k = 0  # 3000원 이하 일수

    for code in codes:
        rows = conn.execute("""
            SELECT date, close, volume FROM daily_ohlcv_long
            WHERE code = ? AND close > 0
            ORDER BY date ASC
        """, (code,)).fetchall()
        if len(rows) < 20:
            continue

        prev_close = None
        for d, c, v in rows:
            prices.append(c)
            vols.append(v)
            if c <= 3000:
                under_3k += 1
            total_days += 1
            if prev_close and prev_close > 0:
                r = (c / prev_close - 1) * 100
                rets.append(r)
                if abs(r) < 0.01:
                    zero_change += 1
            prev_close = c

    if not prices:
        print(f'\n[{label}] 데이터 없음')
        return

    prices = np.array(prices)
    vols = np.array(vols)
    rets = np.array(rets)

    print(f'\n[{label}]')
    print(f'  종목 수: {len(codes)}')
    print(f'  총 관측치: {total_days:,}일')
    print(f'  평균 종가: {prices.mean():>8,.0f}원  '
          f'중앙값: {np.median(prices):>8,.0f}원')
    print(f'  3,000원 이하 일수 비율: {under_3k/total_days*100:>6.2f}%')
    print(f'  평균 거래량: {vols.mean():>10,.0f}주  '
          f'중앙값: {np.median(vols):>10,.0f}주')
    print(f'  일일 수익률 std: {rets.std():>6.3f}%')
    print(f'  변동 없는 날(|ret|<0.01%) 비율: {zero_change/len(rets)*100:>6.2f}%')
    print(f'  극단 하락 일(-5%↓) 비율: {(rets <= -5).sum()/len(rets)*100:>5.2f}%')
    print(f'  극단 상승 일(+5%↑) 비율: {(rets >= 5).sum()/len(rets)*100:>5.2f}%')


measure(available_spacs, '스팩 (SPAC)')
measure(available_reits, '리츠/인프라')
measure(normal_sample, '일반 종목 (샘플 200)')

conn.close()
