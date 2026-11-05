"""Verify deliverable arithmetic, original-text preservation, and vault parity."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
import sys
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[3]
TODAY=ROOT.parents[1]
KST=ZoneInfo('Asia/Seoul')

def fm(text):
    _,header,body=text.split('---',2)
    return yaml.safe_load(header),body.lstrip('\n')

def main():
    final='--final' in sys.argv
    meta=json.loads((TODAY/'meta/koru-review-codex.json').read_text())
    required={'job_id','kind','ticker','model','date','reviewed_date','repo_path','vault_path','vault_written','title','summary','scores','lessons','own_note_updated'}
    assert set(meta)==required
    assert meta['date']=='2026-11-05' and meta['reviewed_date']=='2026-11-04'
    assert meta['repo_path']=='research/2026-11-05/koru-review-codex.md'
    assert meta['vault_path']=='PERSONAL/STOCK/KORU/2026-11-04-review-codex-astra-max.md'
    assert len(meta['scores'])==3 and 3<=len(meta['lessons'])<=5
    d=pd.read_csv(ROOT/'KORU_1m.csv')
    d.index=pd.to_datetime(d.pop('timestamp'),utc=True).dt.tz_convert(KST)
    for s in meta['scores']:
        assert set(s)=={'model','note','base_time_kst','base_price','call','expiry_kst','expiry_price','change_pct','verdict','comment'}
        t=pd.Timestamp(s['expiry_kst'],tz=KST)
        assert pd.Timestamp(s['base_time_kst'],tz=KST)+pd.Timedelta(hours=24)==t
        assert t<pd.Timestamp.now(tz=KST)
        assert abs(float(d.loc[t,'Close'])-s['expiry_price'])<1e-8
        assert abs((s['expiry_price']/s['base_price']-1)*100-s['change_pct'])<1e-6
        assert s['verdict']==('미적중' if s['model']=='Codex Astra Max' else '적중')
    body=(TODAY/'koru-review-codex.md').read_text()
    assert body.splitlines()[0]=='# '+meta['title']
    assert re.findall(r'^## (\d)\.',body,re.M)==['1','2','3','4','5']
    vfront,vbody=fm((ROOT/'review_vault.md').read_text())
    assert vfront['type']=='stock-forecast-review' and vfront['status']=='completed'
    assert str(vfront['date'])=='2026-11-04' and vfront['reviewer']==meta['model']
    state=json.loads((ROOT/'render_state.json').read_text())
    expected=body
    for old,new in state['link_map'].items():
        expected=expected.replace(old,new)
    expected=expected.replace('# '+meta['title']+'\n\n','# '+meta['title']+'\n\n'+state['vault_header'],1)
    assert vbody==expected
    assert not re.search(r'\]\((?:\.\.?/|koru-data/)',vbody)
    before=(ROOT/'own_forecast_repo_before.md').read_text().rstrip()
    now=(REPO/'research/2026-11-04/koru-forecast-24h-astra.md').read_text()
    assert now.startswith(before+'\n\n## 사후 결과 복기\n')
    prior=json.loads((ROOT/'own_forecast_vault_before.json').read_text())['content']
    updated=(ROOT/'own_forecast_vault_updated.md').read_text()
    assert fm(updated)[0]['status']=='completed'
    old_parts=re.split(r'## 6\. 사후 결과 복기\n[\s\S]*?(?=\n---\n\n## 7\.)',prior)
    new_parts=re.split(r'## 6\. 사후 결과 복기\n[\s\S]*?(?=\n---\n\n## 7\.)',updated)
    assert len(old_parts)==len(new_parts)==2
    assert old_parts[0].replace('status: pending\n','status: completed\n',1)==new_parts[0]
    assert old_parts[1]==new_parts[1]
    for t in [body,vbody,now,updated]:
        assert not re.search(r'\{(?:REVIEW|REVIEWED)[^}]*\}',t)
    for target in re.findall(r'\]\(([^)]+)\)',body):
        if not target.startswith(('https://','http://','#')):
            assert (TODAY/target).exists(), target
    files=[p for p in ROOT.rglob('*') if p.is_file()]
    assert all(p.stat().st_size<10_000_000 for p in files)
    if final:
        assert meta['vault_written'] is True and meta['own_note_updated'] is True
        receipt=json.loads((ROOT/'vault_receipts.json').read_text())
        for key,name in [('review','review_vault.md'),('own_forecast','own_forecast_vault_updated.md')]:
            assert receipt[key]['readback_equal'] is True
            assert receipt[key]['content_sha256']==hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    result={'validated_at_kst':datetime.now(KST).isoformat(),'mode':'final' if final else 'preflight',
            'passed':True,'checks':['metadata_schema','expiry_and_returns','four_score_dimensions_documented',
                       'forecast_preservation','repo_vault_body_parity','relative_links','size_limit']+
                      (['mcp_write_readback','completion_flags'] if final else []),
            'artifact_count':len(files),'max_file_bytes':max(p.stat().st_size for p in files)}
    (ROOT/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    main()
