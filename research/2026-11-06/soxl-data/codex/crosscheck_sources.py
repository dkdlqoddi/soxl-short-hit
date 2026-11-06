from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import requests

OUT = Path(__file__).resolve().parent
SOURCES = {
    'nasdaq_soxl': 'https://api.nasdaq.com/api/quote/SOXL/historical?assetclass=etf&fromdate=2026-11-03&todate=2026-11-05&limit=10',
    'yahoo_soxl_query2': 'https://query2.finance.yahoo.com/v8/finance/chart/SOXL?range=5d&interval=1m&includePrePost=true',
    'korea_kospi': 'https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?range=5d&interval=1d',
    'korea_samsung': 'https://query1.finance.yahoo.com/v8/finance/chart/005930.KS?range=5d&interval=1d',
    'korea_hynix': 'https://query1.finance.yahoo.com/v8/finance/chart/000660.KS?range=5d&interval=1d',
    'qualcomm_results': 'https://investor.qualcomm.com/files/content_files/FY2026-4th-Quarter-Earnings-Release.pdf',
    'arm_results': 'https://newsroom.arm.com/news/arm-q2-fye27-results',
    'arm_filing': 'https://investors.arm.com/node/8506/html',
    'soxx_split': 'https://www.sec.gov/Archives/edgar/data/1100663/000119312526430480/d156277d497.htm',
    'bls_productivity': 'https://www.bls.gov/news.release/prod2.nr0.htm',
    'dol_claims': 'https://www.dol.gov/ui/data.pdf',
    'reuters_nov5': 'https://www.fidelity.com/news/article/us-markets/202611051023RTRSNEWSCOMBINED_L6N46M12A_1',
    'cnbc_nov4': 'https://www.cnbc.com/2026/11/03/stock-market-today-live-updates.html',
}

def fetch(item):
    name,url = item
    rec = {'id':name,'url':url,'checked_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'},timeout=30,stream=True)
        rec['http_status']=r.status_code
        chunks=[];size=0
        for chunk in r.iter_content(65536):
            size+=len(chunk)
            if size>9_500_000:
                raise ValueError('Response exceeds artifact size limit')
            chunks.append(chunk)
        raw=b''.join(chunks)
        r.close()
        content_type=r.headers.get('Content-Type','')
        suffix='.pdf' if 'pdf' in content_type else '.json' if 'json' in content_type else '.html'
        rec.update({'content_type':content_type,'filename':name+suffix,'bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest()})
        return rec,raw
    except Exception as exc:
        rec['error']=str(exc)
        return rec,None

def main():
    records=[]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for rec,raw in pool.map(fetch,SOURCES.items()):
            if raw is not None:
                (OUT/rec['filename']).write_bytes(raw)
            records.append(rec)
            print(rec['id'],rec.get('http_status'),rec.get('bytes'),rec.get('error',''),flush=True)
    (OUT/'source_access.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
