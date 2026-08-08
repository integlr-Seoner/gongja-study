"""검증: 거래대금 상위 200이 자격 필터 통과 이후에 추가로 주는 효과
근본: 자격 필터(MIN_PRICE+MIN_VOLUME)를 이미 통과한 universe에서
     거래대금 상위로 추가 제한이 어떤 효과를 주는지 측정.

이전 검증(_v_02/03/04)은 "전체 대비 Top N의 기대수익률"을 봤고,
필터 통과 여부를 고려하지 않았음. 이번 검증은:

  [기준 universe] 자격 필터 통과 종목 (price>=1000, volume>=50000)
  [비교 그룹]    그 중 거래대금 상위 N (50/100/200/500)

질문:
  - 자격 통과 후에도 Top N이 여전히 수익률 열세인가? (이전 검증 재확인)
  - 자격 통과 후 Top N이 '큰 상승 포착'에 여전히 유리한가?
  - 거래대금 상위가 단기 모멘텀(1-5일)엔 유의한지
"""
import sqlite3
import numpy as np

DB = r'D:\StockAnalyst\ohlcv_long.db'
MIN_PRICE = 1000
MIN_VOL = 50000

conn = sqlite3.connect(DB, timeout=30)

all_dates = [r[0] for r in conn.execute("""
    SELECT DISTINCT date FROM daily_ohlcv_long
    WHERE date >= '20140101' AND date <= '20260417'
    ORDER BY date
""").fetchall()]

samples = []
current_ym = ''
for d in all_dates:
    ym, dd = d[:6], int(d[6:8])
    if ym != current_ym and dd >= 15:
        samples.append(d)
        current_ym = ym

print(f'샘플: {len(samples)}개 (2014-01~2026-04 월 단위 중순)')
print()


def get_future_date(asof, n):
    r = conn.execute("""
        SELECT date FROM (
            SELECT DISTINCT date FROM daily_ohlcv_long
            WHERE date > ? ORDER BY date ASC LIMIT ?
        ) ORDER BY date DESC LIMIT 1
    """, (asof, n)).fetchone()
    return r[0] if r else None


N_VALUES = [50, 100, 200, 500]
HOLDS = [1, 5, 20]

# 모든 그룹: 자격 통과한 전체 + 그 중 Top N
results = {'전체(자격통과)': {h: [] for h in HOLDS}}
for N in N_VALUES:
    results[f'Top {N} (자격통과 내)'] = {h: [] for h in HOLDS}

for i, asof in enumerate(samples, 1):
    # 자격 필터 통과한 종목만
    today = conn.execute("""
        SELECT code, close, volume
        FROM daily_ohlcv_long
        WHERE date = ?
          AND close >= ? AND volume >= ?
          AND close BETWEEN low AND high
    """, (asof, MIN_PRICE, MIN_VOL)).fetchall()
    if not today:
        continue

    today_map = {c: p for c, p, _ in today}
    sorted_codes = sorted([(c, p*v) for c, p, v in today], key=lambda x: -x[1])

    # 미래 종가
    fut_maps = {}
    for h in HOLDS:
        fd = get_future_date(asof, h)
        if not fd:
            fut_maps[h] = {}
            continue
        fut_maps[h] = {c: p for c, p in conn.execute("""
            SELECT code, close FROM daily_ohlcv_long
            WHERE date = ? AND close > 0 AND close BETWEEN low AND high
        """, (fd,)).fetchall()}

    # 전체(자격통과)
    for code, p in today_map.items():
        for h in HOLDS:
            fp = fut_maps[h].get(code)
            if fp and p > 0:
                r = (fp/p - 1) * 100
                if -50 <= r <= 100:
                    results['전체(자격통과)'][h].append(r)

    # Top N
    for N in N_VALUES:
        top_codes = [c for c, _ in sorted_codes[:N]]
        for code in top_codes:
            p = today_map.get(code)
            if not p:
                continue
            for h in HOLDS:
                fp = fut_maps[h].get(code)
                if fp and p > 0:
                    r = (fp/p - 1) * 100
                    if -50 <= r <= 100:
                        results[f'Top {N} (자격통과 내)'][h].append(r)

    if i % 30 == 0:
        print(f'  {i}/{len(samples)}')

conn.close()


print()
print('=' * 110)
print('검증: 자격 필터 통과 후 거래대금 상위 N의 추가 효과')
print('=' * 110)
print(f'{"그룹":<22} | {"보유":>4} | {"샘플":>7} | {"평균":>8} | {"중앙":>8} | '
      f'{"승률":>7} | {"5%+":>6} | {"10%+":>6} | {"-5%↓":>6}')
print('-' * 100)

for group in ['전체(자격통과)', 'Top 500 (자격통과 내)',
              'Top 200 (자격통과 내)', 'Top 100 (자격통과 내)',
              'Top 50 (자격통과 내)']:
    for h in HOLDS:
        arr = np.array(results[group][h])
        if len(arr) < 50:
            continue
        up5 = (arr >= 5).sum() / len(arr) * 100
        up10 = (arr >= 10).sum() / len(arr) * 100
        dn5 = (arr <= -5).sum() / len(arr) * 100
        print(f'{group:<22} | {h:>3}d | {len(arr):>7,} | '
              f'{arr.mean():>+7.2f}% | {np.median(arr):>+7.2f}% | '
              f'{(arr > 0).sum()/len(arr)*100:>6.2f}% | '
              f'{up5:>5.2f}% | {up10:>5.2f}% | {dn5:>5.2f}%')
    print()

# 차이 (Top N vs 전체자격통과)
print('=' * 90)
print('자격 필터 통과 universe 대비 Top N의 상대 효과 (%p 차이)')
print('=' * 90)
print(f'{"Top N":<10} {"보유":>4} {"평균Δ":>8} {"승률Δ":>8} {"5%+Δ":>8} {"10%+Δ":>8} {"-5%↓Δ":>8}')
print('-' * 60)

for N in N_VALUES:
    gk = f'Top {N} (자격통과 내)'
    for h in HOLDS:
        base = np.array(results['전체(자격통과)'][h])
        top = np.array(results[gk][h])
        if len(top) < 50 or len(base) < 50:
            continue
        d_avg = top.mean() - base.mean()
        d_win = (top > 0).sum()/len(top)*100 - (base > 0).sum()/len(base)*100
        d_up5 = (top >= 5).sum()/len(top)*100 - (base >= 5).sum()/len(base)*100
        d_up10 = (top >= 10).sum()/len(top)*100 - (base >= 10).sum()/len(base)*100
        d_dn5 = (top <= -5).sum()/len(top)*100 - (base <= -5).sum()/len(base)*100
        print(f'Top {N:<6} {h:>3}d {d_avg:>+7.3f} {d_win:>+7.2f} '
              f'{d_up5:>+7.2f} {d_up10:>+7.2f} {d_dn5:>+7.2f}')
    print()
