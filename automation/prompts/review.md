# 작업: {{ticker}} 직전 회차 24시간 예측 복기

{{ticker_desc}}

## 복기 대상 — {{reviewed_date}} 회차

{{prev_notes}}

{{prev_summaries}}

## 할 일

1. 노트마다 기준 시각·기준가·직전 정규장 종가·만기 시각·방향 판단·상승 확률·중심 예상가·시나리오·재검토선을 뽑습니다.
2. 1분봉(시간외 포함) 실제 시세로 만기 가격을 확인합니다. 만기 시각에 체결이 없으면 직전 마지막 체결가를 씁니다. **만기가 아직 오지 않은 노트는 지금 가격으로 `잠정` 채점하고 남은 시간을 적습니다.**
3. 모델별로 채점합니다: ① 기준가 대비 방향 ② 중심 예상가 범위 ③ 직전 정규장 종가 대비 판단 ④ 시나리오·재검토선이 실제 경로에서 작동했는지. 판정은 `적중`·`미적중`·`부분 적중`·`잠정` 중 하나로 씁니다.
4. 기준 시각부터 만기(필요하면 그 뒤 몇 시간)까지 실제 경로를 국면으로 나누고, 국면마다 동인(뉴스·지표·실적·한국장 등)과 모델 판단이 맞거나 틀린 이유를 분석합니다.
5. 다음 예측에 바로 쓸 교훈 3~5개를 구체적인 규칙으로 적습니다.
6. **본인 직전 노트 갱신**: 위 표의 `{{model_name}}` 노트(저장소·볼트 모두)의 "사후 결과 복기" 절에 만기 실제가·등락률·판정·복기 메모를 채웁니다. 만기가 지났으면 볼트 프론트매터를 `status: completed`로 바꿉니다. 볼트는 `vault_read`로 받은 `version`을 `vault_write`의 `ifMatch`로 넘깁니다. 본인 노트가 없으면 건너뛰고 복기 노트에 그 사실을 적습니다. 다른 모델의 노트는 고치지 않습니다.

## 복기 노트 형식

- 볼트 프론트매터:

  ```yaml
  ---
  type: stock-forecast-review
  ticker: {{ticker}}
  date: {{reviewed_date}}            # 복기 대상 회차
  reviewed_at: "YYYY-MM-DD HH:MM KST"
  reviewer: {{model_name}}
  horizon: 24h
  models: [복기 대상 모델 명칭들]
  status: completed                 # 잠정 채점이 하나라도 있으면 provisional
  tags: [stock, forecast-24h, review, {{ticker}}, {{vault_slug}}]
  ---
  ```

- 제목: `# [{{ticker}}] {{reviewed_date}} 24시간 예측 사후 평가 — {{model_name}}`
- 목차: 1 한눈에 보는 평가 결론 및 채점표 · 2 실제 주가 경로 복기(국면 분해) · 3 모델별 상세 평가(잘한 점·놓친 점) · 4 다음 예측에 쓸 교훈 · 5 참조 문서 및 데이터 출처
- 참고 예시: 볼트 `PERSONAL/STOCK/SOXL/2026-11-03-review.md`

## 메타 JSON 스키마 — `{{meta_path}}`

```json
{
  "job_id": "{{job_id}}",
  "kind": "review",
  "ticker": "{{ticker}}",
  "model": "{{model_name}}",
  "date": "{{date}}",
  "reviewed_date": "{{reviewed_date}}",
  "repo_path": "{{repo_note}}",
  "vault_path": "{{vault_note}}",
  "vault_written": true,
  "title": "노트 H1 제목과 같은 문자열",
  "summary": "README 목록용 1~3문장 요약 (만기 실제가, 모델별 판정, 핵심 교훈)",
  "scores": [
    {
      "model": "복기 대상 모델 명칭 (예: Claude Fable Max)",
      "note": "research/YYYY-MM-DD/....md",
      "base_time_kst": "YYYY-MM-DD HH:MM",
      "base_price": 0.0,
      "call": "예: 하락 소폭 우세 (상승 45%)",
      "expiry_kst": "YYYY-MM-DD HH:MM",
      "expiry_price": 0.0,
      "change_pct": 0.0,
      "verdict": "적중 | 미적중 | 부분 적중 | 잠정",
      "comment": "한 줄 평"
    }
  ],
  "lessons": ["교훈 1", "교훈 2", "교훈 3"],
  "own_note_updated": true
}
```
