"""Check source-derived prices, evaluation boundaries and write scope."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import pandas as pd
import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
repo=ROOT/'research/2026-11-06/soxl-review-codex.md'
fallback=ROOT/'automation/runs/20261106-094235/vault-fallback/soxl-review-codex.md'
meta=json.loads((ROOT/'research/2026-11-06/meta/soxl-review-codex.json').read_text())
checks={}

def check(name,condition):
    assert condition,name
    checks[name]=True

def without_review(s):
    s=re.sub(r'## 6\. 사후 결과 복기\n[\s\S]*?(?=## 7\. 출처 및 원본 참조)','',s)
    return re.sub(r'^status: (pending|completed)$','status: ORIGINAL',s,flags=re.M)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

check('exact_meta_fields',set(meta)==set('job_id kind ticker model date reviewed_date repo_path vault_path vault_written title summary scores lessons own_note_updated'.split()))
check('three_models',len(meta['scores'])==3)
check('five_lessons',len(meta['lessons'])==5)
check('fallback_flags_honest',meta['vault_written'] is False and meta['own_note_updated'] is False)
text=repo.read_text();v=fallback.read_text()
check('fallback_roundtrip',v==(OUT/'review_vault.md').read_text())
fm=yaml.safe_load(v.split('---',2)[1])
check('vault_frontmatter',fm['status']=='completed' and fm['ticker']=='SOXL' and fm['reviewer']=='Codex Astra Max' and str(fm['date'])=='2026-11-05')
check('title_matches_meta',text.splitlines()[0]=='# '+meta['title'])
check('repo_vault_body_parity',v[v.index('# '+meta['title']):]==text)
check('no_unfilled_placeholders','{{' not in text and '{{' not in v)
check('five_required_sections',len(re.findall(r'^## [1-5]\. ',text,re.M))==5)
refs=set(re.findall(r'\[\^([^\]]+)\](?!:)',text))
defs=set(re.findall(r'^\[\^([^\]]+)\]:',text,re.M))
check('footnotes_resolve',refs==defs)
check('wiki_header_present','[[PERSONAL/STOCK/README|' in v)
check('no_repo_relative_markdown_links_in_vault',not re.search(r'\]\((?:\.\.?/|data/|soxl-data/)',v))

previous=ROOT/'research/2026-11-05/forecast-24h-codex.md'
old=(OUT/'own_forecast_repo_before.md').read_text();new=previous.read_text()
check('only_own_review_and_status_changed',without_review(old)==without_review(new))
check('own_repo_completed',yaml.safe_load(new.split('---',2)[1])['status']=='completed')
metrics=json.loads((OUT/'review_metrics.json').read_text())
concurrent_source_changes={}
for f in metrics['forecasts']:
    check(f['slug']+'_input_snapshot_unchanged',sha(OUT/f"original_forecast_{f['slug']}.md")==f['source_sha256'])
    if f['slug']!='codex':
        # Other models may concurrently update their own prior-note review sections.
        # Only compare hashes; do not ingest their new review contents.
        concurrent_source_changes[f['slug']]=sha(ROOT/f['note'])!=f['source_sha256']

s=pd.read_csv(OUT/'SOXL_1m.csv',index_col=0)
s.index=pd.to_datetime(s.index,utc=True)
for score in meta['scores']:
    end=pd.Timestamp(score['expiry_kst'],tz='Asia/Seoul').tz_convert('UTC')
    if score['model']=='Codex Astra Max':
        eligible=s[(s.index+pd.Timedelta(minutes=1)<=end)&(s.volume>0)]
        row=eligible.iloc[-1];actual=float(row.close)
        check('codex_proxy_no_future',row.name.tz_convert('America/New_York').strftime('%H:%M')=='10:04')
    else:
        row=s.loc[end];actual=float(row.open)
    check(score['model']+'_price_from_raw',abs(score['expiry_price']-actual)<.00001)
    check(score['model']+'_return_from_raw',abs(score['change_pct']-(actual/score['base_price']-1)*100)<.000001)
    check(score['model']+'_expired',end<pd.Timestamp.now(tz='UTC'))
check('opening_price_distinct_from_close',abs(float(s.loc[pd.Timestamp('2026-11-05 09:30',tz='America/New_York'),'close'])-56.95)>.5)
for entry in json.loads((OUT/'collection_manifest.json').read_text()):
    check(entry['symbol']+'_'+entry['interval']+'_raw_hash',sha(OUT/entry['raw_file'])==entry['sha256'])

files=[p for p in OUT.rglob('*') if p.is_file()]+[repo,fallback,previous,ROOT/'research/2026-11-06/meta/soxl-review-codex.json']
check('all_files_under_10mb',all(p.stat().st_size<10_000_000 for p in files))
check('chart_present',(OUT/'actual_path.png').stat().st_size>10000)
result={'checked_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
 'passed':len(checks),'checks':checks,'largest_file_bytes':max(p.stat().st_size for p in files),
 'concurrent_source_hash_changes':concurrent_source_changes,
 'repo_sha256':sha(repo),'fallback_sha256':sha(fallback),
 'limitations':['Vault guide/current note/version could not be read; both vault writes and readback remain pending.',
                'Codex exact-second trade unavailable; prior completed minute close used as predeclared.',
                'No new historical backtest or actual trading execution evaluated.']}
(OUT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':len(checks),'largest_file_bytes':result['largest_file_bytes'],
                  'repo_sha256':result['repo_sha256'],'fallback_sha256':result['fallback_sha256']},ensure_ascii=False))
