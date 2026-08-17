# 인계 — 단권화 + KRX/KIS 커넥터 (2026-08-17)

> 새 대화창에서 이 문서를 먼저 읽고 이어서 작업. 대상 = 금융공자/와디즈 학습 코퍼스 + 사례대장 + KRX/KIS MCP 커넥터.
> 저장소: `github.com/integlr-Seoner/gongja-study` (= `D:\StockAnalyst\book_extracts`). 최신 상태 푸시됨.

---

## 0. 한 줄 상태
사례대장 **CASE-0001~0333**(재료매매 49건 추가 완료, 연속·무결). 단권화 패키지 **Stage1+2 완성**. **KRX/KIS MCP 커넥터(`krx`) 6도구 설치·작동 확인**.

---

## 1. 사례대장 / 재료매매 (완료)
- 재료매매는 6트랙 중 **첫 완독 트랙**(가이드북 1~4권, G1~G127). 5·6권+부속이 잔여였고, A(정독)가 완독→`A2B_재료매매_신규후보_인계_G6557.md`(57마커) 인계→B가 **CASE-0285~0333 등록**(전 건 KRX 실측 대조).
- 매각10·경영권3·CES1·정치15·정책11·신선재료9. 재료 소멸/반전 3종(동신건설·국영지앤엠·한국컴퓨터)=실패 라벨.
- dedup: TS트릴리온 탈모약=0253, 보성파워텍 2월말=0090. 코드 오기 4건 정정(수산아이앤티 050960·KMH 122450·화성밸브 039610·베셀 177350).
- 대장 무결성: **0001~0333 연속, 중복0·gap0, 성공271·실패62**.
- 남은 미독 트랙: **조건검색기[LAST]** — 검색기 "제작 해설서" 성격(조건식 레시피), 종목 실사례 희소 → 신규 CASE 거의 없을 것으로 예상. A 완독 시 마커 grep만 하면 됨.

## 2. 단권화 패키지 (`book_extracts/단권화/`) (완료)
- `cases.csv`(UTF-8 BOM)·`cases.json` — 333건 정형(case_id/seq/label/date/name/code/tag_main/tag_sub/tag_full/g_ref/source/evidence).
- `README.md` — 부칙 P 규칙·스키마·태그 상위계열·활용법.
- `개념단권.md` — 핵심 개념 카드(기준봉·적정거래대금·재료·낙폭과대·상따·짝짓기·246·N자·볼밴 등) + 각 개념 **연결 CASE·G앵커** + 트랙간 충돌(C01~03) + 오답지점(E01~04) + 개념→CASE 전체 인덱스.
- `용어대조_금융공자_와디즈.md` — 두 책 용어 대조(세력↔주포·기준봉↔ABCD의 B·N자파동↔ABCD·짝짓기↔커플링·종가관리↔종가배팅[혼용주의]) + 와디즈 실제 종목 예시 + 와디즈 CASE 소급 0건 조사결과.
- `와디즈_종목언급_인덱스.md` — ★사장님 **수기 입력용 워크시트**. 발생일만 채우면 B가 KRX 대조 후 등록. 유망 후보: **에스맥·정다운·오리엔트바이오**(이재명 테마 미등록), **한미글로벌**(네옴시티, p.511).

## 3. 와디즈 미라클 상태
- 정독+보강 완료(`01_와디즈미라클_학습노트.md` + `01b_와디즈_보강.md`, 1,622p 전체).
- **CASE 소급 = 0건**: 와디즈는 명명종목+발생일 실사례를 안 쓰고 거시 사이클·익명 차트·개념 나열로 설명 → 부칙 P(발생일 필수) 미충족. 개념층만 용어대조표로 편입. (조사 2회 완료, 종목코드0·개별발생일0 확인.)

## 4. ★KRX/KIS MCP 커넥터 (핵심 신규 인프라)
로컬 stdio MCP 서버. Cowork에선 `mcp__remote-devices__krx__*`로 노출.
- **파일**: `D:\StockAnalyst\krx_mcp_server.py`(순수 표준라이브러리, 외부 MCP 프레임워크 없음) / `krx_api.py`(KRX Open API, data-dbg) / `.env`(KRX_OPEN_API_KEY). 투자자별은 `D:\Quant\kis_api.py`+`kis_config.json`(KIS 토큰) 재사용.
- **설정**: `C:\Users\integ\AppData\Roaming\Claude\claude_desktop_config.json`의 `mcpServers.krx` 등록됨(command=venv python, args=krx_mcp_server.py).
- **도구 6종**:
  - `find_by_name(name,date,market)` — 특정일 종목명 시세(발생일 대조용)
  - `get_market_by_date(date,market,name_contains,min_value_eok,top)` — 전종목(거래대금순)
  - `get_ohlcv(code,fromdate,todate)` — 기간 일봉
  - `top_movers(date,by,direction,top,min_value_eok)` — 등락률/거래대금 상위
  - `surge_check(code,date,lookback)` — 평소 대비 거래대금·거래량 급증 배수 + 그날 등락률
  - `investor_trend(code,days)` — KIS 국내 투자자별 일별 순매수(개인/외국인/기관계, 수량+억)
- **★한계**: 기관 세부(투신·연기금)는 **어떤 비차단 소스로도 불가**. KRX 포털(MDCSTAT023)=LOGOUT 차단, KIS·Open API=3분류(개인/외국인/기관계)만, pykrx 투자자별=차단(단 pykrx 시세는 내부적으로 네이버라 됨).
- **기기 이동 시**: 클라우드 커넥터 아님(로컬). 새 PC엔 ①코드파일 ②비밀키(.env·kis_config.json, git에 없음) ③파이썬 패키지(requests·pandas·python-dotenv) ④config에 krx 등록 ⑤앱 재시작 필요.

## 5. 다음 후보 작업 (미착수)
- (분석 도구) investor_trend+surge_check 결합: "외국인+기관 동시 순매수일의 익일/3일 수익률", "거래대금 N배 급증일 등락률 분포". → krx 서버에 툴 추가 후 앱 재시작.
- (CASE) 와디즈 수기 인덱스에 발생일 채워지면 에스맥/정다운/오리엔트바이오/한미글로벌 등록.
- (CASE) 조건검색기 트랙 A 완독 시 마커 확인.
- (단권) 이평/246·장기이평 전용 CASE 세분류 → 개념 카드 정밀 연결.

## 6. 운영 규칙 (준수)
- KRX = `krx_api.py`/krx 커넥터(Open API)만. pykrx 투자자별 금지(차단). git은 book_extracts 내부만, 타깃 add, 커밋메시지 특수문자는 `-F` 파일 사용.
- 부칙 P: 발생일 필수·라벨=저자 제시 목적·추측 금지·KRX 실측. 동일종목 발생일 다르면 별건.
