"""Validate numerical, temporal, and artifact invariants for this review."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import re
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
REPORT=REPO/'research/2026-11-06/koru-review-codex.md'
META=REPO/'research/2026-11-06/meta/koru-review-codex.json'
FALLBACK=REPO/'automation/runs/20261106-094235/vault-fallback/koru-review-codex.md'
OWN=REPO/'research/2026-11-05/koru-forecast-24h-codex.md'

def main():
 checks=[]
 def check(label,condition):
  checks.append(dict(check=label,passed=bool(condition)))
 m=json.loads(META.read_text());body=REPORT.read_text();vault=FALLBACK.read_text()
 required={'job_id','kind','ticker','model','date','reviewed_date','repo_path','vault_path','vault_written','title','summary','scores','lessons','own_note_updated'}
 check('metadata exact required keys',set(m)==required)
 check('title equals repository H1',body.splitlines()[0]=='# '+m['title'])
 check('review date and write date remain distinct',m['date']=='2026-11-06' and m['reviewed_date']=='2026-11-05')
 check('all three model scores',len(m['scores'])==3)
 check('three to five lessons',3<=len(m['lessons'])<=5)
 check('five standard top-level sections',len(re.findall(r'^## [1-5]\. ',body,re.M))==5)
 check('no unrendered placeholders','@@' not in body and '@@' not in vault)
 fm=yaml.safe_load(vault.split('---',2)[1])
 check('vault frontmatter completed',fm['status']=='completed' and fm['type']=='stock-forecast-review')
 check('vault target round',str(fm['date'])=='2026-11-05')
 check('vault wikilink header','[[PERSONAL/STOCK/README|' in vault)
 check('vault no repository-relative markdown links',not re.search(r'!?\[[^\]]+\]\((?!https?://|#)[^)]+\)',vault))
 check('fallback equals prepared vault body',vault==(ROOT/'review_vault.md').read_text())
 check('vault availability flags honest',m['vault_written'] is False and m['own_note_updated'] is False)
 scores=json.loads((ROOT/'scores.json').read_text())
 k=pd.read_csv(ROOT/'KORU_1m.csv',index_col=0);k.index=pd.to_datetime(k.index,utc=True).tz_convert('Asia/Seoul')
 raw=json.loads((ROOT/'yahoo_KORU_1m_raw.json').read_text())['chart']['result'][0]
 q=pd.Series(raw['indicators']['quote'][0]['close'],index=pd.to_datetime(raw['timestamp'],unit='s',utc=True).tz_convert('Asia/Seoul'))
 for meta,s in zip(m['scores'],scores):
  expiry=pd.Timestamp(s['expiry_kst'],tz='Asia/Seoul')
  valid=k[(k.index+pd.Timedelta(minutes=1)<=expiry)&k.Close.notna()]
  price=float(valid.iloc[-1].Close);bar=valid.index[-1]
  check(s['model']+' as-of price',math.isclose(price,meta['expiry_price'],abs_tol=1e-9))
  check(s['model']+' no future bar',bar+pd.Timedelta(minutes=1)<=expiry)
  check(s['model']+' direct raw crosscheck',math.isclose(price,float(q.loc[bar]),abs_tol=1e-9))
  check(s['model']+' return arithmetic',abs((price/meta['base_price']-1)*100-meta['change_pct'])<1e-6)
  check(s['model']+' direction label',meta['verdict']=='적중' and price<meta['base_price'])
  check(s['model']+' central range miss',price<s['center'][0] and not s['center_hit'])
  check(s['model']+' expiry passed',expiry<pd.Timestamp.now(tz='Asia/Seoul'))
 own=OWN.read_text();before=(ROOT/'own_forecast_repo_before.md').read_text()
 check('own status completed','status: completed' in own.split('---',2)[1])
 check('own only status and review section changed',
  own.split('## 6. 사후 결과 복기')[0].replace('status: completed','status: pending')==before.split('## 6. 사후 결과 복기')[0]
  and own.split('## 7. 출처 및 원본 참조',1)[1]==before.split('## 7. 출처 및 원본 참조',1)[1])
 check('own original base and probability preserved','base_price: 10.60' in own and '약 45% — 정성적 판단' in own)
 inp=json.loads((ROOT/'forecast_inputs.json').read_text())
 own_input=next(x for x in inp if x['slug']=='codex')
 check('own original hash verified',hashlib.sha256(before.encode()).hexdigest()==own_input['original_sha256'])
 check('own recovery files exist',all((ROOT/f).exists() for f in ['own_forecast_vault_candidate.md','own_forecast_review_section.md','vault_sync_pending.json']))
 check('raw KORU minute data has no split in review window',not k.loc['2026-11-05':'2026-11-06','Stock Splits'].fillna(0).ne(0).any())
 a=json.loads((ROOT/'analysis.json').read_text())
 check('both two-bar confirmations at midnight',all(v['first_confirmed']=='2026-11-06 00:00:00+09:00' for v in a['regular_confirmations'].values()))
 soxx=next(v for v in a['daily'] if v['symbol']=='SOXX')
 check('SOXX split-adjusted calculation',soxx['split_factor']==3 and -13<soxx['change_pct']<-12)
 # Only links in our own report are read; no current-day other-model content is opened.
 for path in re.findall(r'!?\[[^\]]+\]\(([^)]+)\)',body):
  if path.startswith(('http://','https://','#')):continue
  target=(REPORT.parent/path).resolve()
  if target==ROOT/'validation.json':continue
  check('local link '+path,target.exists())
 sizes=[(str(p.relative_to(REPO)),p.stat().st_size) for p in ROOT.rglob('*') if p.is_file()]
 for p in [REPORT,META,FALLBACK,OWN]:sizes.append((str(p.relative_to(REPO)),p.stat().st_size))
 check('every artifact below 10 MB',all(size<10_000_000 for _,size in sizes))
 check('plot artifact exists',(ROOT/'koru_path.png').stat().st_size>10000)
 out=dict(validated_at_kst=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),passed=all(x['passed'] for x in checks),
  checks=checks,artifact_count=len(sizes),max_file=max(sizes,key=lambda x:x[1]),
  known_limitations=['Obsidian MCP unavailable: review fallback created, own previous vault sync pending.',
    'Expiry prices are last completed one-minute aggregates; exact tick timestamps and executable bid/ask unavailable.',
    'Daily closing prices differ across providers; expiry scoring unchanged.',
    'No new backtest or trading execution was performed.'])
 (ROOT/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'passed':out['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']],
    'artifact_count':len(sizes),'max_file':out['max_file']},ensure_ascii=False,indent=2))
 assert out['passed']

if __name__=='__main__':main()
