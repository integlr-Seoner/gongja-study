# 인계 — KRX/KIS 수급 분석 커넥터 (2026-08-17)

> 단권화/사례대장 트랙과 분리된 **수급 분석 인프라** 문서. 새 대화창에서 수급 분석을 이어갈 때 이 문서를 읽는다.

---

## 0. 사장님 연구 목표 (출발점)
> "등락률 상위·거래대금 급증 스캔도 필요하고, 기관과 외국계의 움직임도 중요하다. 특히 내가 생각하는 것은 **기관과 외국인의 매수나 매도가 동시에 발생되었을 때의 주가의 변화**, **평소 대비 어느 정도의 변화가 주가에 급격한 변동을 일으키는지**, 기관 중에서도 예를 들어 **투신이나 연기금 등 특정 투자 주체의 거래변동이 주가에 미치는 영향**을 알아보고 싶다."

## 1. 목표 → 도구 매핑 (현재 가능/불가)
| 연구 질문 | 도구 | 상태 |
|---|---|---|
| 등락률·거래대금 상위 스캔 | `top_movers` | ✅ |
| 평소 대비 거래대금/거래량 급증 배수 → 주가 변동 | `surge_check` | ✅ |
| 기관·외국인 동시 매수/매도 → 주가 변화 | `investor_trend`(일별 개인/외국인/기관계 순매수+종가) | ✅ |
| 평소 대비 순매수 임계 | `investor_trend` 시계열 + `surge_check` | ✅(분석은 후처리) |
| **투신·연기금 등 세부 주체별 영향** | — | ❌ **비차단 소스 없음**(§3) |

## 2. 커넥터 개요 (`krx` MCP 서버)
로컬 stdio MCP 서버. Cowork에선 `mcp__remote-devices__krx__*`로 노출.
- **파일**: `D:\StockAnalyst\krx_mcp_server.py`(순수 표준라이브러리) · `krx_api.py`(KRX Open API) · `.env`(KRX_OPEN_API_KEY). 투자자별은 `D:\Quant\kis_api.py`+`kis_config.json`(KIS 토큰) 재사용.
- **설정**: `claude_desktop_config.json`의 `mcpServers.krx` 등록됨. 서버 수정 시 **앱 재시작**해야 반영.

## 3. ★투자자별 데이터 소스 조사 결론 (재론 금지)
- **KRX Open API(AUTH_KEY, data-dbg)** = 시세/지수/기본정보만. **투자자별 미제공**.
- **KRX 포털 통계(MDCSTAT022/023, 투신·연기금 세부 O)** = 프로그램 접근 시 **`LOGOUT`(400) 차단**. pykrx 투자자별이 이 때문에 실패(빈/에러). ※pykrx의 "시세"가 되던 건 내부적으로 **네이버**에서 가져오기 때문(KRX 아님).
- **KIS(한국투자 REST, TR `FHKST01010900`)** = **개인/외국인/기관계 3분류** 일별 순매수(수량+거래대금) O. 토큰 방식이라 **차단 없음·안정적**. 단 **투신/연기금 세부는 미제공**.
- **결론**: 안정적으로 얻을 수 있는 최대 granularity = **3분류(개인/외국인/기관계)**. 투신·연기금 세부는 KRX 포털 전용인데 차단이라 **어떤 비차단 API로도 불가**. (정말 필요하면 실제 로그인 브라우저로 KRX 화면 스크래핑뿐 — 취약, 비권장.)

## 4. 도구 상세
- `find_by_name(name, date, market)` — 특정일 종목명(부분일치) 시세. 반환: code,open,high,low,close,change_pct,volume,value(원),value_eok(억),market_cap.
- `get_market_by_date(date, market, name_contains, min_value_eok, top)` — 전종목(거래대금 내림차순). 필터 권장.
- `get_ohlcv(code, fromdate, todate)` — 기간 일봉 OHLCV.
- `top_movers(date, by, direction, top, min_value_eok)` — by=change_pct|value, direction=up|down. 등락률/거래대금 상위.
- `surge_check(code, date, lookback=20)` — lookback일 평균 대비 target일 **거래대금·거래량 배수** + 그날 등락률. (일자별 조회라 lookback만큼 소요)
- `investor_trend(code, days=30)` — KIS 국내 투자자별 **최근 약 30영업일** 일별 순매수. 필드: date, close, prdy_vrss, indiv/foreign/inst_net_qty(주), indiv/foreign/inst_net_eok(억). ※최근 30영업일 고정(임의 과거 구간은 이 TR로는 제한).

## 5. 실측 관찰 (삼성전자, 참고)
- **외국인+기관 동시 순매수일 → 급등**(예: 2026-07-31 외국인+2.10조·기관+0.94조 → 종가 +55,500). **동시 순매도일 → 급락**(예: 2026-08-03 외국인−0.95조·기관−1.22조 → −23,000). 개인은 대체로 반대편. → 사장님 "동시성" 가설과 부합.
- `surge_check` 예: 에코프로 2024-03-15 = 거래대금 0.47배(평소 절반, 한산) → 등락률 −1.31%. 급증일(상한가·장대양봉)에 넣으면 배수 1 초과.

## 6. 다음 분석 도구 (미착수 — krx 서버에 추가 후 앱 재시작)
- **동시성 수익률**: "외국인+기관 동시 순매수일의 익일/3일/5일 수익률 분포" (investor_trend + get_ohlcv 결합).
- **급증일 수익률 분포**: "거래대금 N배 이상 급증일의 당일·익일 등락률 분포" (surge_check 로직 배치화).
- **평소 대비 Z-score**: 투자자별 순매수를 N일 평균/표준편차 대비 Z-score로 → 급변일 탐지·임계 도출(사장님 "평소 대비 임계" 질문 직접 대응).
- (임의 과거 구간 투자자별이 필요하면 KIS의 기간 조회 TR/누적 저장 방식 검토.)

## 7. 운영 / 기기 이동
- `krx`는 **클라우드 커넥터 아님(로컬 서버)**. 새 PC에선 ①코드파일(krx_mcp_server.py·krx_api.py·kis_api.py) ②비밀키(**.env·kis_config.json, git에 없음 → 수동 복사**) ③파이썬 패키지(requests·pandas·python-dotenv) ④config에 krx 등록 ⑤앱 재시작 — 5개 다 갖춰야 도구가 뜬다.
- 규칙: KRX=Open API/krx 커넥터만. **pykrx 투자자별 금지(차단)**.
