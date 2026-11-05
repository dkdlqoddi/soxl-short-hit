# 작업: {{ticker}} 24시간 주가 방향 예측

{{ticker_desc}}

## 공통 기준 (세 모델 동일)

| 항목 | 값 |
| --- | --- |
| 기준 시각 | **{{base_kst}} KST** ({{base_et}}) |
| 만기 | **{{expiry_kst}} KST** ({{expiry_et}}) — 기준 시각 + 24시간 |
| 기준 시각의 세션 | {{base_session_desc}} |
| 시세 스냅샷 (오케스트레이터, yfinance) | {{snapshot}} |

- 기준가는 기준 시각의 1분봉 종가(시간외 포함)입니다. 스냅샷이 있으면 그 값을 기준가로 쓰고, 명백히 틀렸다면 직접 확인한 값을 쓰되 둘 다 적습니다.
- 만기 시각에 체결이 없으면 직전 마지막 체결가로 판정합니다.
- 기준가 이중 병기: ① 기준가 대비 방향·상승 확률 ② 직전 정규장 종가 대비 방향·상승 확률을 따로 냅니다.
- 분석하는 동안 기준 시각 이후 가격을 봤다면 "분석 시점 추가 확인"으로 따로 적고, 판단은 기준가 기준으로 냅니다.

## 할 일

1. 오늘 쓴 본인 복기 노트가 있으면 먼저 읽고 교훈을 반영합니다: {{own_review}} — 다른 모델의 오늘 노트는 읽지 않습니다.
2. 이전 본인 예측 노트: {{own_prev_note}}
3. 시세·뉴스·일정을 모읍니다: {{ticker}}와 기초지수·관련 종목, 지수 선물, 환율, VIX, 간밤·오늘 주요 뉴스, 향후 24시간 일정(실적·경제지표·연준·한국장 등).
4. 정량 분석: 장기 일봉 조건부 통계, 단기 분봉·시간외 통계, 최근 레짐(급락장·조정장 등) 실제 사례 대조. 표본 수(N)를 밝히고 과적합을 경계합니다.
5. 확률 합 100%인 시나리오와 가격대, 상·하방 재검토(무효화) 기준, 향후 24시간 일정표(KST/ET)를 만듭니다.
6. 결론: 기준가 대비 방향, 상승 확률(%), 중심 예상가 범위, 확신도. 직전 정규장 종가 대비 판단도 따로 적습니다.

## 노트 형식

- 볼트 가이드 "표준 양식 B — 모델별 상세 분석 노트"의 프론트매터와 7절 목차를 그대로 씁니다. 프론트매터: `type: stock-forecast-model`, `ticker: {{ticker}}`, `date: {{date}}`, `horizon: 24h`, `model: {{model_name}}`, `base_time_kst`, `base_session`, `base_price`, `prev_close`, `forecast_end_kst: "{{expiry_kst}}"`, `stance`, `up_prob`, `confidence`, `status: pending`, `tags`(`{{vault_slug}}` 포함).
- 제목: `# [{{ticker}}] 24시간 주가 방향 분석 — {{model_name}} ({{date}})`
- 6절 "사후 결과 복기"는 만기 전이므로 `진행 중`으로 남깁니다.
- 볼트 노트 헤더 링크: 통합 비교 `[[PERSONAL/STOCK/{{ticker}}/{{date}}]]`(오케스트레이터가 만듦), 가이드, 같은 날짜 다른 모델 노트(`{{date}}-claude-fable-max`, `{{date}}-codex-astra-max`, `{{date}}-antigravity-argon-high`), 본인 복기 노트.

## 메타 JSON 스키마 — `{{meta_path}}`

```json
{
  "job_id": "{{job_id}}",
  "kind": "forecast",
  "ticker": "{{ticker}}",
  "model": "{{model_name}}",
  "date": "{{date}}",
  "repo_path": "{{repo_note}}",
  "vault_path": "{{vault_note}}",
  "vault_written": true,
  "title": "노트 H1 제목과 같은 문자열",
  "summary": "README 목록용 1~3문장 요약 (기준가, 방향, 상승 확률, 중심가, 확신도, 핵심 근거)",
  "base_time_kst": "{{base_kst}}",
  "base_session": "premarket | regular | aftermarket | closed",
  "base_price": 0.0,
  "prev_close": 0.0,
  "expiry_kst": "{{expiry_kst}}",
  "stance": "상승 우세 | 상승 소폭 우세 | 중립 | 하락 소폭 우세 | 하락 우세",
  "up_prob_pct": 50,
  "up_prob_vs_prev_close_pct": 50,
  "center_range": "$0.00~0.00",
  "confidence": "낮음 | 보통~낮음 | 보통 | 높음",
  "invalidation": "상방·하방 재검토 기준 한 줄",
  "market_view": "시황·기술적·구조적 진단 한 줄",
  "key_stats": ["핵심 정량 근거 1~3개 (N·상승 비율 포함)"],
  "key_events": ["MM/DD HH:MM KST 이벤트 (향후 24시간 핵심 일정 2~5개)"],
  "methods": "데이터·방법론 한 줄"
}
```
