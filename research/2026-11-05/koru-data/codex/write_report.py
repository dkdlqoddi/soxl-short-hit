"""Render only the four authorized deliverables and own prior review section.

Vault candidates are uploaded with the MCP separately; initial metadata flags
remain false until both writes are read back and checked.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
TODAY = ROOT.parents[1]
KST = ZoneInfo('Asia/Seoul')
ET = ZoneInfo('America/New_York')
TITLE = '[KORU] 2026-11-04 24시간 예측 사후 평가 — Codex Astra Max'

def main():
    now = datetime.now(KST)
    reviewed = now.strftime('%Y-%m-%d %H:%M')
    reviewed_et = now.astimezone(ET).strftime('%Y-%m-%d %H:%M')
    body = (ROOT/'review_body.md').read_text().replace('{{REVIEWED_AT}}',reviewed).replace('{{REVIEWED_ET}}',reviewed_et)
    (TODAY/'koru-review-codex.md').write_text(body)
    vault_body = body
    mapping = {
        '[저장소 예측](../2026-11-04/koru-forecast-24h-claude.md)': '[[PERSONAL/STOCK/KORU/2026-11-04-claude-fable-max|Claude Fable Max 예측]]',
        '[저장소 예측](../2026-11-04/koru-forecast-24h-astra.md)': '[[PERSONAL/STOCK/KORU/2026-11-04-codex-astra-max|Codex Astra Max 예측]]',
        '[저장소 예측](../2026-11-04/koru-forecast-24h-argon.md)': '[[PERSONAL/STOCK/KORU/2026-11-04-antigravity-argon-high|Antigravity Argon High 예측]]',
        '[KORU 전체 경로와 만기 확대 차트](koru-data/codex/koru_path.png)': 'KORU 전체 경로와 만기 확대 차트 — 저장소 경로: `research/2026-11-05/koru-data/codex/koru_path.png`',
    }
    for old,new in mapping.items():
        vault_body = vault_body.replace(old,new)
    header = ('> 상위 가이드: [[PERSONAL/STOCK/README|공통 정리 형식]] · 회차 통합: [[PERSONAL/STOCK/KORU/2026-11-04|2026-11-04 3모델 비교]]\n'
              '> 평가 원문: [[PERSONAL/STOCK/KORU/2026-11-04-claude-fable-max|Claude Fable Max]] · [[PERSONAL/STOCK/KORU/2026-11-04-codex-astra-max|Codex Astra Max]] · [[PERSONAL/STOCK/KORU/2026-11-04-antigravity-argon-high|Antigravity Argon High]]\n\n')
    vault_body = vault_body.replace('# '+TITLE+'\n\n','# '+TITLE+'\n\n'+header,1)
    fm = ('---\ntype: stock-forecast-review\nticker: KORU\ndate: 2026-11-04\n'
          f'reviewed_at: "{reviewed} KST"\nreviewer: Codex Astra Max\nhorizon: 24h\n'
          'models: [Claude Fable Max, Codex Astra Max, Antigravity Argon High]\nstatus: completed\n'
          'tags: [stock, forecast-24h, review, KORU, codex-astra-max]\n---\n\n')
    (ROOT/'review_vault.md').write_text(fm+vault_body)

    own_section = f'''| 항목 | 내용 |
| --- | --- |
| **복기 확인 시각** | {reviewed} KST / {reviewed_et} EST |
| **예측 만기 시각** | 2026-11-05 08:43 KST / 2026-11-04 18:43 EST |
| **기준 가격 / 직전 정규장 종가** | $11.41 / $11.01 |
| **만기 실제 가격** | **$10.38** — 만기분 Yahoo 1분봉 종가; 직전 완료 08:42 KST / 18:42 EST 분봉도 $10.38 |
| **기준가 대비 등락률** | **-9.03%**（10.38 / 11.41 - 1） |
| **직전 정규장 종가 대비 등락률** | **-5.72%**（10.38 / 11.01 - 1） |
| **방향 적중 여부** | **미적중** — 상승 소폭 우세였으나 실제 하락; 검증 완료 |
| **중심가·수치 확률·종가 대비 별도 전망** | 원문 미제시로 채점 제외. 사후에 새 목표가나 확률을 만들지 않음 |
| **왕복 수수료 0.5% 단순 차감** | 가상 매수 보유 시 약 **-9.53%**; 실제 거래수익이 아니며 환전·스프레드 제외 |
| **복기 메모** | 한국 반도체는 상승 출발했지만 11/4 삼성 218,000원(-0.68%)·SK하이닉스 1,396,000원(-0.14%)으로 하락 마감. 두 종목 모두 전일 종가 아래인 첫 동시 분봉은 11/4 10:11 KST / 11/3 20:11 EST였다. 반등 실패라는 재검토 사유는 발생했지만 철회 시각·가격을 사전에 정하지 않았으므로 최초 상승 판단을 소급 변경하지 않는다. 선반영된 반등을 추가 수익과 구분하지 못했고, 미국 SOXX -3.14%·MU -7.00%와 다음 날 NXT 약세가 겹쳤다. |
| **데이터 확인·한계** | 2026-11-05 13:22:26 KST / 2026-11-04 23:22:26 EST 조회, prepost=True·auto_adjust=False. 시간외 거래량 0은 미제공으로 취급. 1분봉 집계이며 개별 틱·스프레드는 미확인. |

**후속 규칙:** 한국 반도체 반등 유지 여부를 정해진 시각·가격으로 검증하고, EWY·SOXX·MU의 동시 반응과 이미 오른 시간외 기준가를 함께 평가한다. 이 규칙은 개선 제안이며 별도 백테스트는 수행하지 않았다.

전체 복기: {{REVIEW_LINK}}. 원시 자료: 저장소 경로 `research/2026-11-05/koru-data/codex/`.
'''
    repo_own = REPO/'research/2026-11-04/koru-forecast-24h-astra.md'
    before = repo_own.read_text()
    snapshot = ROOT/'own_forecast_repo_before.md'
    if not snapshot.exists():
        snapshot.write_text(before)
    prefix = before.split('\n## 사후 결과 복기\n')[0].rstrip()
    repo_section = own_section.replace('{REVIEW_LINK}','[2026-11-04 회차 사후 평가](../2026-11-05/koru-review-codex.md)')
    repo_own.write_text(prefix+'\n\n## 사후 결과 복기\n\n'+repo_section)

    original = json.loads((ROOT/'own_forecast_vault_before.json').read_text())
    vault_section = own_section.replace('{REVIEW_LINK}','[[PERSONAL/STOCK/KORU/2026-11-04-review-codex-astra-max|2026-11-04 회차 사후 평가]]')
    updated, count = re.subn(r'## 6\. 사후 결과 복기\n[\s\S]*?(?=\n---\n\n## 7\.)',
                            '## 6. 사후 결과 복기\n\n'+vault_section,original['content'],count=1)
    assert count==1
    updated = updated.replace('status: pending\n','status: completed\n',1)
    (ROOT/'own_forecast_vault_updated.md').write_text(updated)
    analysis = json.loads((ROOT/'analysis.json').read_text())
    calls = ['하락 소폭 우세 (상승 약 45%)','상승 소폭 우세 (확률 미제시)',
             '하락 우세 (상승 35~40%; 시나리오 합계 37%)']
    comments = [
      '방향 적중; 중심 $11.00~11.40 및 직전 종가 대비 상승 판단은 미적중. 15% 하방 구간에 도달.',
      '상승 방향 미적중; 한국 반도체 반등 실패 조건은 발생했으나 철회 가격·시각이 미제시. 중심가·별도 종가 전망은 채점 제외.',
      '두 기준의 방향 적중; 중심 $10.80~11.10은 미적중. 20% 하방 구간에 도달; $11.56 초과 분봉 종가는 없음.',
    ]
    scores=[]
    for i,f in enumerate(analysis['forecasts']):
        scores.append({'model':f['model'],'note':f"research/2026-11-04/koru-forecast-24h-{f['slug']}.md",
          'base_time_kst':f['base_time'],'base_price':f['base_price'],'call':calls[i],
          'expiry_kst':f['expiry'],'expiry_price':f['expiry_price'],'change_pct':round(f['change_pct'],6),
          'verdict':f['verdict'],'comment':comments[i]})
    lessons=[
      '시간외 기준가와 직전 정규장 종가의 방향·중심가를 분리하고 선반영된 한국장 반등을 추가 수익에 중복 가산하지 않는다.',
      '삼성전자·SK하이닉스 반등 실패를 가격과 09:30·15:30 KST 점검시각으로 정의하고 외국인 수급과 함께 상승 전망을 재검토한다.',
      'S&P500·나스닥 상승과 반도체 강세를 구분하고 EWY·SOXX·MU를 5분 이내 동시각 자료로 확인한다.',
      '재검토선의 접촉·안착·재이탈 판단 단위를 사전에 고정하고 시간외 가격 한 번의 접촉을 매매 성과로 간주하지 않는다.',
      'NXT·KRX 개장과 만기를 구분하고 중심가·하방 시나리오·왕복 0.5% 비용·분봉 채점 규칙을 사전에 기록한다.',
    ]
    meta={'job_id':'koru-review-codex','kind':'review','ticker':'KORU','model':'Codex Astra Max',
          'date':'2026-11-05','reviewed_date':'2026-11-04','repo_path':'research/2026-11-05/koru-review-codex.md',
          'vault_path':'PERSONAL/STOCK/KORU/2026-11-04-review-codex-astra-max.md','vault_written':False,
          'title':TITLE,'summary':'만기분 실제가는 Claude $10.30(-9.57%), Codex $10.38(-9.03%), Argon $10.3297(-8.59%)로, 방향은 Claude·Argon 적중, Codex 미적중이다. Claude·Argon의 중심 예상가는 모두 미적중이며 한국 반도체의 반등 지속성·선반영 가격·미국 반도체와 전체 지수의 차이를 분리해야 한다.',
          'scores':scores,'lessons':lessons,'own_note_updated':False}
    (TODAY/'meta').mkdir(exist_ok=True)
    (TODAY/'meta/koru-review-codex.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    state={'reviewed_at_kst':reviewed,'reviewed_at_est':reviewed_et,'vault_ifMatch':original['version'],
           'repo_original_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),
           'link_map':mapping,'vault_header':header}
    (ROOT/'render_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'repo_note':str(TODAY/'koru-review-codex.md'),'reviewed_at_kst':reviewed,
                      'vault_candidates':['review_vault.md','own_forecast_vault_updated.md'],
                      'metadata_flags':'awaiting MCP write/read verification'},ensure_ascii=False))

if __name__=='__main__':
    main()
