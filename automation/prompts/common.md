# SOXL·KORU 24시간 예측 실험 — 공통 지시

세 모델(Claude Fable Max · Codex Astra Max · Antigravity Argon High)이 이 지시를 똑같이 받아 동시에, 서로 독립적으로 수행합니다. 사용자는 세 모델의 판단과 적중률을 날마다 비교합니다.

**이번 실행에서 당신은 `{{model_name}}`입니다.** 저장소 파일 슬러그는 `{{repo_slug}}`, 볼트 파일 슬러그는 `{{vault_slug}}`입니다.

비대화형 자동 실행이라 사용자에게 질문하거나 승인을 기다릴 수 없습니다. 판단이 필요한 부분은 합리적으로 정하고 그 이유를 노트에 적은 뒤, 아래 "4. 산출물"을 모두 만들고 종료하세요.

## 1. 실행 정보

| 항목 | 값 |
| --- | --- |
| 실행 ID / 작업 ID | `{{run_id}}` / `{{job_id}}` |
| 작업 | {{task_label}} |
| 작업 시작 | {{task_start_kst}} KST ({{task_start_et}}) |
| 노트 날짜 (한국 날짜) | {{date}} |
| 저장소 | `{{repo_dir}}` (현재 작업 디렉터리, git 저장소) |
| 볼트 | Obsidian — `obsidian` MCP 서버 (`vault_list`, `vault_read`, `vault_write`, `vault_patch`, `vault_append`, `search_simple`) |
| 미국 시장 ({{date}} 밤 거래일) | {{us_sessions}} |
| 한국 시장 | 정규장 09:00~15:30 KST · 넥스트레이드 프리마켓 08:00~08:50, 애프터마켓 15:40~20:00 KST · 코스피200 야간선물(CME) 18:00~06:00 KST |

사용자는 한국에 사는 개인 투자자로, SOXL·KORU 같은 3배 레버리지 ETF를 한국 시간에 맞춰 거래하며 왕복 수수료 0.5%를 냅니다. 노트는 한국어로 쓰고, 시각은 KST를 먼저 적고 미국 동부시간(EST/EDT)을 함께 적습니다.

## 2. 작성 규칙

- 먼저 obsidian MCP로 볼트의 `PERSONAL/STOCK/README.md`(공통 정리 형식 가이드)를 읽고 따릅니다: 프론트매터, 표준 목차, 기준가 이중 병기(시간외 기준가 대비 / 직전 정규장 종가 대비), KST·ET 병기, 재검토(무효화) 조건, 사후 복기 분리(`status: pending | completed`).
- 저장소 `research/` 아래 기존 노트와 볼트 `PERSONAL/STOCK/{{ticker}}/`의 기존 노트를 참고해 형식과 깊이를 맞춥니다. 볼트 노트는 저장소 노트와 같은 본문에 프론트매터와 상단 위키링크 헤더를 붙인 형태입니다.
- 숫자는 직접 확인한 데이터로만 씁니다. 백테스트에는 표본 수(N)·상승 비율·평균/중앙값을 함께 적고, 추정과 확인을 구분합니다. 뉴스·공시·일정은 출처 URL을 마지막 절에 모읍니다.
- 시세는 몇 분 사이에도 바뀝니다. 각 데이터를 확인한 시각(KST)을 적습니다.

## 3. 데이터 소스 참고 (이 환경에서 동작 확인됨)

- Python은 `python3`를 그대로 씁니다(pandas·numpy·yfinance·matplotlib이 사용자 site-packages에 있음). `python3 -I`로 실행하면 패키지를 못 찾아 깨집니다.
- yfinance: `yf.Ticker(sym).history(period="5d", interval="1m", prepost=True)`(1분봉, 시간외 포함), `period="60d", interval="5m"`, `period="730d", interval="1h", prepost=True`(2년 1시간봉), `period="max", interval="1d"`(장기 일봉). 인덱스는 미국 동부시간입니다.
- Nasdaq 일봉 API(브라우저 User-Agent 필요): `https://api.nasdaq.com/api/quote/{{ticker}}/historical?assetclass=etf&fromdate=2010-01-01&todate=YYYY-MM-DD&limit=10000`. stooq는 막혀 있습니다.
- 한국 실시간(네이버 모바일 JSON, 브라우저 User-Agent): `https://m.stock.naver.com/api/index/KOSPI/basic`, `https://m.stock.naver.com/api/stock/005930/basic`(삼성전자), `.../000660/basic`(SK하이닉스). `overMarketPriceInfo`에 넥스트레이드 프리·애프터마켓 가격이 있습니다.
- 코스피200 야간선물: `https://mkospi.com/`, `https://www.prekospi.com/`. 해외 대용: SK하이닉스 ADR `SKHY`, 삼성전자 GDR `SMSN.IL`(런던).
- KORU는 EWY 일간 수익률의 3배를 추적하므로, 미국 날짜 D의 KORU·EWY는 한국 날짜 D+1 코스피와 같은 정보를 담는 경우가 많습니다. 날짜를 맞출 때 주의하세요.

## 4. 산출물 (모두 필수)

1. **저장소 노트**: `{{repo_note}}`
2. **볼트 노트**: obsidian MCP `vault_write`로 `{{vault_note}}`에 저장하고, `vault_read`로 다시 읽어 확인합니다. 저장소 상대 링크는 `[[PERSONAL/STOCK/...]]` 위키링크나 저장소 경로 표기로 바꿉니다.
3. **메타 JSON**: `{{meta_path}}` — 작업 지시의 스키마를 채운 JSON 객체 하나(UTF-8, 주석 없음). 오케스트레이터가 README 목록·통합 비교 노트·커밋 메시지를 이 파일로 만듭니다.
4. **데이터·스크립트**: `{{work_dir}}/` 아래에만 저장합니다(다른 모델 파일과 섞이지 않게). 10MB가 넘는 파일은 만들지 않습니다.

obsidian MCP를 쓸 수 없으면(도구가 없거나 계속 실패) 볼트 노트 전체 내용을 `{{vault_fallback}}`에 저장하고 메타 JSON의 `vault_written`을 `false`로 둡니다. 오케스트레이터가 대신 올립니다.

## 5. 하지 말 것

- `git add`·`git commit`·`git push`, 브랜치 변경 — 모든 모델이 끝난 뒤 오케스트레이터가 한 번에 커밋·푸시합니다.
- 저장소 `README.md`, 볼트 `PERSONAL/STOCK/README.md`, 통합 비교 노트(볼트 `PERSONAL/STOCK/<TICKER>/YYYY-MM-DD.md`, 저장소 `research/<날짜>/<ticker>-summary.md`) 수정 — 오케스트레이터가 갱신합니다.
- `research/{{date}}/`와 볼트에서 오늘 다른 모델이 쓰는 노트를 열거나 고치기 — 독립성을 지킵니다. 직전 회차 노트는 읽어도 됩니다.
- 위 산출물 경로 밖에 파일 만들기 (복기 작업의 "본인 직전 노트 갱신"은 예외)
