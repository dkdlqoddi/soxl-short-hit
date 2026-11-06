"""Render review, scoped own-note update and conservative vault fallback artifacts."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
TODAY=ROOT/'research/2026-11-06'
FALLBACK=ROOT/'automation/runs/20261106-094235/vault-fallback/soxl-review-codex.md'
KST=ZoneInfo('Asia/Seoul')
now=datetime.now(KST)
reviewed=now.strftime('%Y-%m-%d %H:%M')
reviewed_et=now.astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M')
metrics=json.loads((OUT/'review_metrics.json').read_text())
title='[SOXL] 2026-11-05 24시간 예측 사후 평가 — Codex Astra Max'
repo_path='research/2026-11-06/soxl-review-codex.md'
vault_path='PERSONAL/STOCK/SOXL/2026-11-05-review-codex-astra-max.md'
previous_vault='PERSONAL/STOCK/SOXL/2026-11-05-codex.md'

section=f'''## 6. 사후 결과 복기

> 복기: {reviewed} KST / {reviewed_et} EST · 평가자: Codex Astra Max.
> 전체 평가: 저장소 `research/2026-11-06/soxl-review-codex.md` · 볼트 목표 `PERSONAL/STOCK/SOXL/2026-11-05-review-codex-astra-max.md`.

| 평가 항목 | 실제 결과 |
| --- | --- |
| 상태 | **completed — 두 평가 만기 모두 경과** |
| 비교 기준 개장가 | 원문 **$70.00** 유지. 당시 Yahoo 원시값 $70.025와 구별 |
| 개장부터 24시간 뒤 가격 | **2026-11-05 23:30 KST / 11/5 09:30 EST, 다음 개장가 $56.95**, $70.00 대비 **−18.64%** |
| 주 예측 만기 | **2026-11-06 00:05:06 KST / 11/5 10:05:06 EST** |
| 주 만기 평가가 | **$51.17**. 원문 약속에 따라 **00:04~00:05 KST / 10:04~10:05 EST의 마지막 완성 1분봉 종가** 사용. 원시값 `51.16999816894531`, 거래량 `1,627,933` |
| 주 평가 수익률 | `(51.16999816894531 / 70.00 - 1) × 100` = **−26.90%** |
| 분석 당시 $71.75 대비 | **−28.68%** |
| 직전 정규장 종가 $73.12 대비 | **−30.02%** |
| 왕복 0.5%p 비용 단순 차감 | 원문 기준가 보유 손익 **약 −27.40%**, 실제 거래 성과 아님 |
| ① 기준가 방향 | **미적중** — 상승 약 55%와 반대로 하락. 공통 개장 만기로 바꿔도 미적중 |
| ② 중심 예상가 $71~73 | **미적중** — 하단보다 $19.83 낮음 |
| ③ 직전 정규장 종가 대비 | **적중** — 원문의 미회복 판단 부합 |
| ④ 시나리오·재검토선 | **부분 적중** — `$66.50 미만` 분류에 해당하나 대표 하단 $61보다 $9.83 낮음. 상승 철회 조건은 만기 전에 충족 |
| 종합 판정 | **미적중** |

**실제 경로와 복기 메모:** 11/5 00:44~00:45 KST / 11/4 10:44~10:45 EST 봉에서 SOXL 종가 $67.18과 SOXX 보정 종가 $150.7633이 각각 $67.26·$150.82(분할 전 $452.46)를 함께 하회했다. 이어 **00:45·01:00 KST / 10:45·11:00 EST의 15분봉 종가 $67.18·$64.575**로 두 봉 연속 하회가 확정됐다. 정규장 종가 $66.68, 시간외 마지막 분봉 $64.0099, 다음 개장 $56.95로 이어졌다. 장중 평균회귀 기대보다 업종 상대 약세·실적 후 매도·한국 반도체 추가 하락이 강했다. 무효화선은 유효했지만 최초 상승 판단과 중심 범위는 실패했다. 조건 발동은 사후 확인한 것이며, 그때 실시간 전망을 수정하거나 실제로 거래했다는 기록은 아니다.

**측정 한계:** 정확한 만기 초의 체결 자료는 확보하지 못했다. 만기 뒤 체결이 섞이는 00:05~00:06 KST / 10:05~10:06 EST 봉 종가 $50.5971은 채택하지 않았다. 만기 이후 종가·시간외 현재가로 점수를 바꾸지 않았다. 자료 확인은 **2026-11-06 09:44 KST / 11/5 19:44 EST**, [Yahoo SOXL 1분봉](https://query1.finance.yahoo.com/v8/finance/chart/SOXL?range=5d&interval=1m&includePrePost=true)과 [Stock Analysis 개장가](https://stockanalysis.com/etf/soxl/history/)를 사용했다. 원본과 계산은 `research/2026-11-06/soxl-data/codex/`에 보존했다.

**볼트 동기화:** 이번 실행에서 저장소 갱신은 완료했다. Obsidian MCP 접속 불가로 볼트 원문은 현재 version을 읽거나 ifMatch 갱신·재읽기하지 못했다. 이전 볼트 갱신 후보와 해당 절은 같은 데이터 폴더에 별도로 보존했다.

'''
(OUT/'own_forecast_review_section.md').write_text(section,encoding='utf-8')
previous=ROOT/'research/2026-11-05/forecast-24h-codex.md'
original=previous.read_text(encoding='utf-8')
before=OUT/'own_forecast_repo_before.md'
if not before.exists():before.write_text(original,encoding='utf-8')
assert original.count('## 6. 사후 결과 복기')==1
assert original.count('## 7. 출처 및 원본 참조')==1
updated=re.sub(r'## 6\. 사후 결과 복기\n[\s\S]*?(?=## 7\. 출처 및 원본 참조)',lambda _:section,original)
fm_end=updated.index('\n---',4)
front=updated[:fm_end]
assert re.search(r'^status: (pending|completed)$',front,re.M)
front=re.sub(r'^status: (pending|completed)$','status: completed',front,flags=re.M)
updated=front+updated[fm_end:]
previous.write_text(updated,encoding='utf-8')

# Candidate only: current vault content/version has not been read.
front_end=updated.index('\n---',4)+len('\n---')
vault_header=('\n\n> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · '
              '복기: [[PERSONAL/STOCK/SOXL/2026-11-05-review-codex-astra-max|사후 평가]]\n')
candidate=updated[:front_end]+vault_header+updated[front_end:]
candidate=candidate.replace('`data/','`research/2026-11-05/data/')
(OUT/'own_forecast_vault_updated.md').write_text(candidate,encoding='utf-8')

body=(OUT/'review_body.md').read_text(encoding='utf-8').replace('{{REVIEWED_KST}}',reviewed).replace('{{REVIEWED_ET}}',reviewed_et)
(ROOT/repo_path).write_text(body,encoding='utf-8')
frontmatter=f'''---
type: stock-forecast-review
ticker: SOXL
date: 2026-11-05
reviewed_at: "{reviewed} KST"
reviewer: Codex Astra Max
horizon: 24h
models: [Claude Fable Max, Codex Astra Max, Antigravity Argon High]
status: completed
tags: [stock, forecast-24h, review, SOXL, codex-astra-max]
---

'''
header=('> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · '
        '복기 대상 회차: [[PERSONAL/STOCK/SOXL/2026-11-05|2026-11-05]] · '
        '본인 예측: [[PERSONAL/STOCK/SOXL/2026-11-05-codex|Codex 원문]]\n'
        '> 저장소 원본: `research/2026-11-06/soxl-review-codex.md`\n\n')
vault=frontmatter+header+body
(OUT/'review_vault.md').write_text(vault,encoding='utf-8')
FALLBACK.parent.mkdir(parents=True,exist_ok=True)
FALLBACK.write_text(vault,encoding='utf-8')

comments={
 'claude':'하락 방향·직전 종가 미회복 적중, 중심 $67~70과 최하방 $60 이탈; 첫 1시간 버킷은 재조회 분봉에서 재현되지 않음.',
 'codex':'주 만기는 00:05:06 KST; 원문 규칙에 따른 00:04~00:05 완성 1분봉 대용값. 방향·중심 미적중, 철회 조건은 01:00 KST에 확정.',
 'argon':'상승 59%·중심 $71.5~74 미적중, 직전 종가 미회복과 붕괴 경고 유효; 최하방 $61도 이탈.'}
scores=[]
for f in metrics['forecasts']:
    call = ('완만한 상승 우위 (상승 합산 59%, 원문 요약 58~60%)' if f['slug']=='argon'
            else f['direction']+f" (상승 {f['up_prob']*100:.0f}%)")
    scores.append({'model':f['model'],'note':f['note'],'base_time_kst':'2026-11-04 23:30',
      'base_price':f['base'],'call':call,
      'expiry_kst':f['expiry_kst'],'expiry_price':round(f['expiry_price'],2),
      'change_pct':round(f['change_pct'],6),'verdict':f['verdict'],'comment':comments[f['slug']]})
lessons=[
 '기준 시각·정보 마감·만기·가격 측정법을 별도 고정하고 개장 Open과 만기 뒤 봉을 구분한다.',
 '첫 1시간은 09:30≤t<10:30 EST로 집계하고 10:29 분봉까지 완성된 뒤 통계를 적용하며 시가 근처에서는 중립 완충 구간을 둔다.',
 '업종 상대 약세와 무효화선이 동반되면 확률 변경 시각·가격을 기록하고 VIX 하락만으로 반등 가중치를 유지하지 않는다.',
 '실적 후 가격 반응·한국장·다음 프리마켓을 순서대로 재평가하고 대표 가격대 밖 하방 꼬리를 별도 표시한다.',
 '분할 보정·누락 봉·출처 차이를 검증하고 기준가별 수익률과 왕복 비용 0.5%를 분리 기록한다.'
]
meta={'job_id':'soxl-review-codex','kind':'review','ticker':'SOXL','model':'Codex Astra Max',
      'date':'2026-11-06','reviewed_date':'2026-11-05','repo_path':repo_path,'vault_path':vault_path,
      'vault_written':False,'title':title,
      'summary':'공통 만기 개장가는 $56.95(−18.68%), Codex 주 만기는 직전 완성 1분봉 대용 $51.17(−26.90%)이다. Claude는 부분 적중, Codex·Argon은 미적중이다. 핵심 교훈은 만기·봉 경계 고정, 무효화 후 확률 갱신, 하방 꼬리와 분할 보정의 명시다.',
      'scores':scores,'lessons':lessons,'own_note_updated':False}
(TODAY/'meta').mkdir(exist_ok=True)
(TODAY/'meta/soxl-review-codex.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

pending={'reason':'Obsidian MCP unavailable; no fresh read/version; no write attempted',
 'review':{'target':vault_path,'full_content_fallback':str(FALLBACK.relative_to(ROOT)),
           'vault_written':False,'vault_readback_verified':False},
 'previous_forecast':{'target':previous_vault,'repo_updated':True,'vault_updated':False,
    'section_file':str((OUT/'own_forecast_review_section.md').relative_to(ROOT)),
    'full_candidate_file':str((OUT/'own_forecast_vault_updated.md').relative_to(ROOT)),
    'required_procedure':'vault_read current content/version; preserve all sections except section 6 and status; set status completed; vault_write with ifMatch = returned version; vault_read verify',
    'ifMatch':None},
 'own_note_updated_meaning':'False because both repository and vault completion were requested; repository alone is complete.'}
(OUT/'vault_sync_pending.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'repo_note':repo_path,'fallback':str(FALLBACK.relative_to(ROOT)),
                  'meta':'research/2026-11-06/meta/soxl-review-codex.json',
                  'own_repo_updated':True,'own_vault_updated':False,'reviewed_at':reviewed},ensure_ascii=False))
