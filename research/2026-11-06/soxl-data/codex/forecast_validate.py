"""Audit forecast contracts and recompute reported frequencies from saved rows."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
meta=json.loads((REPO/'research/2026-11-06/meta/soxl-forecast-codex.json').read_text())
metrics=json.loads((ROOT/'forecast_metrics.json').read_text())
note=(REPO/meta['repo_path']).read_text()
vault=(ROOT/'forecast_vault.md').read_text()
checks=[]
def check(name,ok,detail=None):
    checks.append({'check':name,'passed':bool(ok),'detail':detail})
    assert ok, name

required={'job_id','kind','ticker','model','date','repo_path','vault_path','vault_written','title','summary',
          'base_time_kst','base_session','base_price','prev_close','expiry_kst','stance','up_prob_pct',
          'up_prob_vs_prev_close_pct','center_range','confidence','invalidation','market_view','key_stats',
          'key_events','methods'}
check('Metadata exactly matches requested field set',set(meta)==required)
check('Numeric metadata is finite',all(np.isfinite(meta[k]) for k in ['base_price','prev_close','up_prob_pct','up_prob_vs_prev_close_pct']))
base=pd.Timestamp(meta['base_time_kst'],tz='Asia/Seoul');end=pd.Timestamp(meta['expiry_kst'],tz='Asia/Seoul')
check('Forecast expiry exactly 24 hours after base',end-base==pd.Timedelta(hours=24))
check('Base and expiry EST conversions',base.tz_convert('America/New_York').strftime('%Y-%m-%d %H:%M %Z')=='2026-11-05 20:42 EST' and end.tz_convert('America/New_York').strftime('%Y-%m-%d %H:%M %Z')=='2026-11-06 20:42 EST')
check('H1 agrees with metadata',re.search(r'^# (.+)$',note,re.M).group(1)==meta['title'])
sections=re.findall(r'^## ([1-7])\. (.+)$',note,re.M)
check('Exactly seven guide sections',[x[0] for x in sections]==list('1234567'),sections)
fm=yaml.safe_load(note.split('---',2)[1]);vfm=yaml.safe_load(vault.split('---',2)[1])
check('Repository and vault frontmatter agree',fm==vfm)
check('Forecast remains pending',fm['status']=='pending' and '진행 중' in note.split('## 6. ')[1].split('## 7.')[0])
check('Frontmatter prices and probabilities agree',fm['base_price']==meta['base_price'] and fm['prev_close']==meta['prev_close'] and fm['up_prob']=='45%' and fm['up_prob_vs_prev_close']=='62%')
filtered='\n'.join(line for line in vault.splitlines() if not line.startswith(('> 통합 비교:','> 같은 날짜 모델별 노트:','> 본인 복기:')))
normalize=lambda s:re.sub(r'\n{3,}','\n\n',s).strip()
check('Vault full body equals repository except wiki header',normalize(filtered)==normalize(note))
check('Required wiki links present',all(x in vault for x in [
 '[[PERSONAL/STOCK/SOXL/2026-11-06|',
 '[[PERSONAL/STOCK/README|',
 '[[PERSONAL/STOCK/SOXL/2026-11-06-claude-fable-max|',
 '[[PERSONAL/STOCK/SOXL/2026-11-06-codex-astra-max|',
 '[[PERSONAL/STOCK/SOXL/2026-11-06-antigravity-argon-high|',
 '[[PERSONAL/STOCK/SOXL/2026-11-05-review-codex-astra-max|']))
sc=note.split('### 5.1 ')[1].split('### 5.2 ')[0]
probs=[int(x) for x in re.findall(r'^\| [^|]+ \| \*\*(\d+)%\*\* \|',sc,re.M)]
check('Scenario sum and both threshold probabilities',sum(probs)==100 and sum(probs[-2:])==meta['up_prob_pct'] and sum(probs[-3:])==meta['up_prob_vs_prev_close_pct'],probs)
defs=set(re.findall(r'^\[\^([^\]]+)\]:',note,re.M));refs=set(re.findall(r'\[\^([^\]]+)\]',note))
check('All source references defined',defs==refs,sorted(refs))
check('All external source URLs grouped in section 7','https://' not in note.split('## 7.')[0])

d=pd.read_csv(ROOT/'forecast_daily_features.csv',index_col=0)
check('Unique daily sessions and no missing close',len(d)==4191 and d.index.is_unique and d.close.notna().all())
v=d[d.next_24h&(d.ret<=-.1)&(d.ratio20<1)].next_ret.dropna()
stat=metrics['daily_stats']['drop10_belowma20_exact24h']
check('Recomputed daily count/win/mean/median',len(v)==stat['N'] and np.isclose((v>0).mean()*100,stat['up_pct']) and np.isclose(v.mean()*100,stat['mean_pct']) and np.isclose(v.median()*100,stat['median_pct']))
check('Current session has no invented outcome',pd.isna(d.iloc[-1].next_ret) and metrics['daily_stats']['drop_as_severe_as_today']['N']==0)
for interval,key in [('1h','hourly_stats'),('5m','five_min_stats')]:
    s=pd.read_csv(ROOT/f'forecast_sessions_{interval}.csv',index_col=0)
    endpoint=pd.to_datetime(s.endpoint,utc=True);nxt=pd.to_datetime(s.next_endpoint,utc=True)
    valid=s.next_24h&s.next_ah_ret.notna()
    check(f'{interval}: one row per session',s.index.is_unique)
    check(f'{interval}: every scored endpoint is 24h apart and known by cutoff',((nxt[valid]-endpoint[valid])==pd.Timedelta(hours=24)).all() and (nxt[valid]<=base).all())
    val=s.loc[valid,'next_ah_ret'];ss=metrics[key]['all_exact24h']
    check(f'{interval}: reported statistics recomputed',len(val)==ss['N'] and np.isclose((val>0).mean()*100,ss['up_pct']) and np.isclose(val.mean()*100,ss['mean_pct']) and np.isclose(val.median()*100,ss['median_pct']))
    repairs=json.loads((ROOT/f'forecast_endpoint_repairs_{interval}.json').read_text())
    check(f'{interval}: missing endpoint repairs came from 1m bars',sum(x['added_missing_session'] for x in repairs)==3 and all('19:59:00' in x['one_min_bar'] for x in repairs))

q=pd.read_csv(ROOT/'forecast_raw/SOXL_5d_1m.csv');row=q[q.time_et=='2026-11-05 19:59:00-05:00'].iloc[0]
check('Base snapshot verified against exact completed 1m row',round(row.close,2)==meta['base_price'])
m=json.loads((ROOT/'forecast_raw/SOXL_5d_1m.json').read_text())['data']['chart']['result'][0]['meta']
check('Previous close verified against stamped metadata',m['regularMarketPrice']==meta['prev_close'] and pd.Timestamp(m['regularMarketTime'],unit='s',tz='UTC').tz_convert('Asia/Seoul').strftime('%Y-%m-%d %H:%M')=='2026-11-06 06:00')
files=[p for p in ROOT.rglob('*') if p.is_file() and 'forecast_' in str(p)]
check('Every new data/script artifact is below 10 MB',all(p.stat().st_size<10_000_000 for p in files),{'files':len(files),'max_bytes':max(p.stat().st_size for p in files)})
receipt=ROOT/'forecast_vault_receipt.json'
if meta['vault_written']:
    r=json.loads(receipt.read_text())
    check('Vault was read back and matched byte-for-byte',r['readback_equal'] and r['sha256']==hashlib.sha256(vault.encode()).hexdigest())
out={'validated_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'passed':True,'checks':checks,
     'repo_sha256':hashlib.sha256(note.encode()).hexdigest(),'vault_sha256':hashlib.sha256(vault.encode()).hexdigest(),
     'vault_written':meta['vault_written']}
(ROOT/'forecast_validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':True,'checks':len(checks),'vault_written':meta['vault_written'],'repo_sha256':out['repo_sha256']},ensure_ascii=False))
