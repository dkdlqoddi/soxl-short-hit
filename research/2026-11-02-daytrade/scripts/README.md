# 재현 방법 (TradingView headless 자동화)

모든 백테스트는 사용자의 TradingView(Premium) 계정에서 headless Chrome으로 실행했다. 사람이 보는 창 없이 백그라운드 로컬 서버가 Pine Editor에 스크립트를 붙여 넣고 결과를 Pine Logs에서 읽어 온다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `pw.js` | 로그인된 Chrome 프로필 복사본으로 headless Chrome을 띄우는 공통 설정 (Node Playwright 1.65, `channel: 'chrome'`) |
| `server.js` | 브라우저 하나를 계속 켜 두고 `POST http://127.0.0.1:8765/run`으로 받은 JS 본문을 실행하는 하네스 서버 |
| `step.sh`, `hdr.js`, `run.sh` | 하네스에 단계 스크립트를 보내는 셸 도우미 (`step.sh`는 `tvlib.js` 로더를 앞에 붙임) |
| `tvlib.js` | TradingView UI 조작 함수: 간격 변경, 스크립트 붙여넣기, "Add/Update on chart", 컴파일 결과 읽기, 가상 스크롤되는 Pine Logs 전체 읽기 |
| `screen.pine` | **1단계 스크리너.** 매수 20 × 매도 20 조건으로 210 × 210 = 44,100 조합을 배치로 봉마다 시뮬레이션하고 결과를 Pine Logs로 내보내는 인디케이터. `randomMode`를 켜면 매수 조건이 난수 비트로 바뀜(무작위 대조) |
| `strategy.pine` | **2단계 확인용 전략.** 같은 조건 정의를 `strategy()`로 옮긴 것. 입력: 매수 A/B, 매도 A/B 번호(−1 = 없음), 익절·손절·트레일링·샹들리에·시간 청산·최대 보유시간. 결과(요약·거래 목록·일별 자산)를 Pine Logs로 내보냄 |
| `bench.pine`, `logtest.pine` | Pine 루프 처리량과 로그 길이 한계를 잰 벤치마크 |
| `s_runner_start.js` | 1단계 러너: 시간봉별 배치 계획대로 `screen.pine`을 돌려 `out/screen/screen_<tf>_b<k>.txt` 저장 (중단 뒤 재시작하면 있는 파일은 건너뜀) |
| `s_random_start.js` | 무작위 대조 러너 (15분·1시간봉) → `random_<tf>_b<k>.txt` |
| `s_confirm_start.js` | 2단계 러너: `jobs.json`의 조합을 `strategy.pine`으로 하나씩 실행 → `out/confirm/<id>.txt` |
| `parse_logs.py`, `analyze.py` | 1단계 로그 → `data/screen_<tf>.csv`, `top_<tf>.csv`, `robust_buy/sell_<tf>.csv`, `singles_<tf>.csv`, `random_<tf>.csv` (저장소에는 44,100행짜리 `screen_*`·`random_*`를 `.csv.gz`로 압축해 두었음; `gunzip -k` 로 풀면 됨) |
| `make_jobs.py` | 1단계 결과에서 2단계 확인 목록(`jobs.json`) 생성: 상위·강건 매수/매도·칼마·범주별 최고·기준선·파라미터 이웃 |
| `parse_confirm.py` | 2단계 로그 → `data/confirm_summary.csv`, `confirm_trades.csv`, `confirm_equity.csv` (뒤 둘은 저장소에서 `.csv.gz`) |
| `timeofday.py` | 확인된 전략의 거래를 KST 시간대로 바꿔 진입·청산 시각 분포 계산 |
| `tables.py`, `charts.py`, `build_note_stage2.py`, `fix_tables.py` | 노트용 마크다운 표·그림·2단계 절 생성, 표 안 OR 기호 수리 |
| `chain1.sh`~`chain3.sh` | 러너를 순서대로 잇는 백그라운드 대기 스크립트 |

## 순서

```bash
# 1) 하네스 (로그인된 프로필을 scratchpad/tv/profile 로 복사한 뒤)
node server.js &            # headless Chrome + HTTP 하네스
./step.sh s_runner_start.js  # 1단계 전수 스크리닝 (약 25분, 진행 상황 out/runner.log)
./step.sh s_random_start.js  # 무작위 대조 (약 10분)
# 2) 분석
python3 analyze.py out/screen data
python3 make_jobs.py data out/confirm/jobs.json 15,30,60,120,5
./step.sh s_confirm_start.js # 2단계 Strategy Tester 확인 (약 30분, out/confirm/runner.log)
python3 parse_confirm.py out/confirm out/confirm/jobs.json data
python3 timeofday.py data data/timeofday.csv
python3 tables.py data data > tables.md && python3 fix_tables.py tables.md   # 표 안의 "A | B"를 "A ∣ B"로
python3 charts.py data data charts
```

TradingView 쪽 전제: 차트당 20,000봉(Premium), Pine 실행 한도 40초. 스크리너 배치 크기는 봉 수에 맞춰 조정(15분봉 4,000, 30분봉 6,000, 1·2시간봉 10,000, 5분봉 3,000).
