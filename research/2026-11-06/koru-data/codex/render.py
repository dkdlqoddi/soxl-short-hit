"""Write the authorized review artifacts and update only our previous forecast."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
TODAY=REPO/'research/2026-11-06'
TITLE='[KORU] 2026-11-05 24시간 예측 사후 평가 — Codex Astra Max'
REVIEW_REPO='research/2026-11-06/koru-review-codex.md'
REVIEW_VAULT='PERSONAL/STOCK/KORU/2026-11-05-review-codex-astra-max.md'
FALLBACK=REPO/'automation/runs/20261106-094235/vault-fallback/koru-review-codex.md'
OWN=REPO/'research/2026-11-05/koru-forecast-24h-codex.md'

def dump(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def repo_links(text,base):
 # Unknown vault paths remain explicit repository paths; never invent a vault file.
 def replace(m):
  image_mark,label,path=m.group(1),m.group(2),m.group(3)
  if path.startswith(('https://','http://','#')):return m.group(0)
  absolute=(base/path).resolve()
  relative=str(absolute.relative_to(REPO))
  return f'{label}: 저장소 `{relative}`'
 return re.sub(r'(!?)\[([^\]]+)\]\(([^)]+)\)',replace,text)

def main():
 now=datetime.now(ZoneInfo('Asia/Seoul'))
 kst=now.strftime('%Y-%m-%d %H:%M');et=now.astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M')
 body=(ROOT/'review_body.md').read_text().replace('@@REVIEWED_KST@@',kst).replace('@@REVIEWED_EST@@',et)
 (REPO/REVIEW_REPO).write_text(body,encoding='utf-8')
 fm=f'''---
type: stock-forecast-review
ticker: KORU
date: 2026-11-05
reviewed_at: "{kst} KST"
reviewer: Codex Astra Max
horizon: 24h
models: [Claude Fable Max, Codex Astra Max, Antigravity Argon High]
status: completed
tags: [stock, forecast-24h, review, KORU, codex-astra-max]
---

'''
 header=('> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · 회차 통합: [[PERSONAL/STOCK/KORU/2026-11-05|2026-11-05 회차]]\n'
        f'> 저장소 원본: `{REVIEW_REPO}` · 볼트 연결 실패 시 업로드용 대체 사본\n\n')
 vault_body=repo_links(body,TODAY).replace('# '+TITLE+'\n\n','# '+TITLE+'\n\n'+header,1)
 vault=fm+vault_body
 (ROOT/'review_vault.md').write_text(vault,encoding='utf-8')
 FALLBACK.parent.mkdir(parents=True,exist_ok=True)
 FALLBACK.write_text(vault,encoding='utf-8')
 backup=ROOT/'own_forecast_repo_before.md'
 if not backup.exists():backup.write_bytes(OWN.read_bytes())
 before=backup.read_text()
 section=f'''## 6. 사후 결과 복기

복기 기록: **{kst} KST / {et} EST**, Codex Astra Max. 1분봉은 **2026-11-06 09:44:24~28 KST / 2026-11-05 19:44:24~28 EST** 수집했으며, 원래 기준가와 확률·중심가·시나리오는 수정하지 않았다.

| 평가 항목 | 기록 |
| --- | --- |
| 상태 | **완료 — completed**, 만기 경과·남은 시간 0분 |
| 기준 시각과 가격 | **11/5 07:33:38 KST / 11/4 17:33:38 EST, $10.60** |
| 만기 | **11/6 07:33:38 KST / 11/5 17:33:38 EST** |
| 만기 실제 시간외 가격 | **$6.3400** — 만기 전 마지막 완료 1분봉의 종가 |
| 선택한 봉 | **11/6 07:32:00~07:32:59 KST / 11/5 17:32:00~17:32:59 EST**, 07:33:00 KST / 17:33:00 EST 완료; 만기와 봉 완료의 차이 38초 |
| 주 평가 수익률 | `(6.34 / 10.60 - 1) × 100` = **-40.19%** |
| 직전 정규장 종가 대비 | `(6.34 / 10.43 - 1) × 100` = **-39.21%** |
| 방향 판단 | **적중** — $10.60 대비 약한 하락 우세(상승 약 45%) |
| 중심 예상가 | **미적중** — $10.30~10.55 하단보다 **$3.96 낮음** |
| 직전 종가 대비 중립 판단 | **미적중** — 보합을 크게 벗어난 하락 |
| 시나리오·재검토 | **부분 적중** — `<$10.07` 하락 분류 및 KORU/EWY 하방 확인 조건 성립; 대표 가격대 $9.20~10.00는 미달 |
| 수수료 참고 | 기준가 매수·만기 매도를 가정한 단순 0.5%p 차감 수익률 **-40.69%**; 실제 거래 성과 아님 |

**복기 메모:** 한국장 반도체 약세와 외국인 매도라는 방향 근거는 맞았지만, 한국장 급락 뒤 미국 반도체와 시장 전체가 함께 급락하는 두 번째 충격을 과소평가했다. 코스피는 5,383.80(-5.28%), 삼성전자 -7.57%, SK하이닉스 -9.46%로 마감했고, 미국 MU는 Yahoo 일봉 기준 -17.46%였다. ‘소폭 하락’ 중심가와 종가 대비 중립은 실패했다.

KORU와 EWY는 **11/5 09:06 KST / 11/4 19:06 EST 봉**에서 모두 하방선 아래였으나 시간외 양방향 호가는 확보하지 못했다. 정규장 두 개의 완료 15분봉 확인은 **11/6 00:00 KST / 11/5 10:00 EST**에 성립했고, 당시 두 번째 봉 종가는 KORU **$8.2597**, EWY **$141.71**이었다. 이미 대표 하방 범위를 벗어난 상태이므로 향후에는 신호 확인 시 새 기준가·가격 범위를 별도 예측으로 저장한다. 실제 자동 갱신·주문 실행은 없었다.

**측정 한계:** 개별 체결의 초 단위 원장은 없어 만기 정확한 마지막 틱을 확인한 것은 아니다. 만기 뒤 체결을 배제하려고 마지막 완료봉을 사용했다. Yahoo 시간외 거래량 0을 무체결로 단정하지 않았다. 07:33 라벨 봉 전체 종가 $6.3399를 쓴 민감도 결과도 판정은 같다. 공급자 분봉 기준 평가는 완료했으며 실행 가능한 호가·틱 가격의 검증과 구분한다.

상세 근거와 출처: [2026-11-05 회차 사후 평가](../2026-11-06/koru-review-codex.md). 11/5 미국 정규장 종가에는 Yahoo $6.53·Stock Analysis $6.51 차이가 있으나 주 평가는 이 종가 대신 고정된 $10.43과 만기 분봉 $6.34를 사용했다. 볼트 동기화는 MCP 연결 실패로 미완료이며, 저장소 갱신과 별도 기록한다.

'''
 (ROOT/'own_forecast_review_section.md').write_text(section,encoding='utf-8')
 updated,n=re.subn(r'## 6\. 사후 결과 복기\n.*?(?=## 7\. 출처 및 원본 참조)',lambda m:section,before,flags=re.S)
 assert n==1
 updated,n=re.subn(r'^status: pending$', 'status: completed',updated,count=1,flags=re.M)
 assert n==1
 OWN.write_text(updated,encoding='utf-8')
 own_vault=repo_links(updated,OWN.parent)
 own_vault=own_vault.replace('model: Codex\n','model: Codex Astra Max\n',1)
 own_vault=own_vault.replace('# KORU 11월 5일 한국장 개장 전 현재가 기준 24시간 전망\n\n',
  '# KORU 11월 5일 한국장 개장 전 현재가 기준 24시간 전망\n\n'
  '> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · 복기: [[PERSONAL/STOCK/KORU/2026-11-05-review-codex-astra-max|사후 평가]]\n'
  '> 저장소 원본에서 생성한 복구 후보. 실제 볼트 원문·버전은 미확인.\n\n',1)
 (ROOT/'own_forecast_vault_candidate.md').write_text(own_vault,encoding='utf-8')
 scores=json.loads((ROOT/'scores.json').read_text())
 comments={
 'Claude Fable Max':'방향 적중; 중심·종가 대비 상승은 미적중. D 조건은 발생했으나 $8.80 하단도 미달; 원문 만기 24시간 2분.',
 'Codex Astra Max':'방향 적중; 중심·종가 대비 중립은 미적중. 하락 분류와 두 15분봉 확인은 성립했으나 $9.20 대표 하단을 크게 하회.',
 'Antigravity Argon High':'방향 적중; 중심·종가 대비 중립은 미적중. $10.23/$10.03 이탈은 유효했으나 $9.10 하방 범위도 하회.'}
 lessons=[
 '한국장 마감과 미국장 첫 두 15분봉 뒤에 새 기준가·중심가·범위를 별도 예측으로 저장한다.',
 '하방 분류 적중과 가격 범위 적중을 분리하고, 범위 하단 이탈 시 기존 범위의 무효를 기록한다.',
 '과매도 반등에는 한국 반도체·외국인 현물 수급·EWY·분할 보정 SOXX의 회복 확인 조건을 붙인다.',
 '만기 전 마지막 완료봉·KST/EST·시장·공급자·분할을 고정하고 시세 공백과 종가 차이를 공개한다.',
 '방향 적중과 매매 성과를 분리하고 왕복 비용 0.5% 및 실제 체결 여부를 함께 기록한다.'
 ]
 meta=dict(job_id='koru-review-codex',kind='review',ticker='KORU',model='Codex Astra Max',
  date='2026-11-06',reviewed_date='2026-11-05',repo_path=REVIEW_REPO,vault_path=REVIEW_VAULT,
  vault_written=False,title=TITLE,
  summary='만기 전 마지막 완료 1분봉은 Claude $6.38(-39.92%), Codex $6.34(-40.19%), Argon $6.3501(-39.98%)로 세 모델 모두 방향은 적중했지만 중심가·하방 가격 범위는 미적중했다. 한국장 급락과 미국 반도체 추가 충격을 분리하고 재검토선 이탈 시 가격 범위를 다시 산정해야 한다.',
  scores=[dict(model=s['model'],note=s['note'],base_time_kst=s['base_time_kst'][:16],base_price=s['base_price'],
     call=s['call'],expiry_kst=s['expiry_kst'][:16],expiry_price=s['expiry_price'],change_pct=round(s['change_pct'],6),
     verdict=s['verdict'],comment=comments[s['model']]) for s in scores],lessons=lessons,own_note_updated=False)
 dump(TODAY/'meta/koru-review-codex.json',meta)
 sync=dict(recorded_at_kst=now.isoformat(),mcp_available=False,
  failure='MCP initialize failed at http://127.0.0.1:27123/mcp/; direct HTTP and HTTPS MCP connections also refused',
  guide_read=False,review_vault_written=False,review_target=REVIEW_VAULT,
  review_fallback=str(FALLBACK.relative_to(REPO)),review_fallback_sha256=hashlib.sha256(vault.encode()).hexdigest(),
  own_repo_updated=True,own_vault_updated=False,own_note_updated=False,
  own_vault_candidates=['PERSONAL/STOCK/KORU/2026-11-05-codex.md','PERSONAL/STOCK/KORU/2026-11-05-codex-astra-max.md'],
  own_vault_version=None,own_vault_ifMatch_used=None,
  instructions=['vault_list로 직전 본인 노트의 실제 경로를 확인한다.',
  'vault_read로 원문 및 version을 받아 원문의 사후 결과 복기 절과 status만 갱신한다. candidate 전체로 무조건 덮어쓰지 않는다.',
  'vault_write의 ifMatch에는 그 읽기에서 얻은 version을 전달한다.',
  'vault_read 재검증 후 own_note_updated를 true로 바꾼다.'],
  candidate=str((ROOT/'own_forecast_vault_candidate.md').relative_to(REPO)),
  section=str((ROOT/'own_forecast_review_section.md').relative_to(REPO)))
 dump(ROOT/'vault_sync_pending.json',sync)
 dump(ROOT/'render_state.json',dict(reviewed_at_kst=kst,reviewed_at_est=et,
  own_before_sha256=hashlib.sha256(before.encode()).hexdigest(),own_after_sha256=hashlib.sha256(updated.encode()).hexdigest(),
  review_repo_sha256=hashlib.sha256(body.encode()).hexdigest(),vault_fallback_sha256=hashlib.sha256(vault.encode()).hexdigest()))
 print(json.dumps({'repo':REVIEW_REPO,'fallback':str(FALLBACK.relative_to(REPO)),
   'meta':'research/2026-11-06/meta/koru-review-codex.json','own_repo_updated':True,'own_vault_updated':False},ensure_ascii=False))

if __name__=='__main__': main()
