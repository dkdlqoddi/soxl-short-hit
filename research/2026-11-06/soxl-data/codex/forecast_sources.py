from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib,json,requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'forecast_sources'
DEST.mkdir(exist_ok=True)
SOURCES={
 'stockanalysis_soxl':'https://stockanalysis.com/etf/soxl/history/',
 'direxion':'https://www.direxion.com/product/daily-semiconductor-bull-bear-3x-etfs',
 'bls_schedule':'https://www.bls.gov/schedule/2026/11_sched.htm',
 'fed_schedule':'https://www.federalreserve.gov/newsevents/2026-november.htm',
 'umich':'https://www.sca.isr.umich.edu/',
 'qcom':'https://www.sec.gov/Archives/edgar/data/804328/000080432826000127/qcom092726erex991.htm',
 'arm':'https://newsroom.arm.com/news/arm-q2-fye27-results',
 'microchip':'https://ir.microchip.com/news-events/press-releases/detail/1426/microchip-technology-announces-financial-results-for-second-quarter-of-fiscal-year-2027',
 'reuters_close':'https://ca.marketscreener.com/news/trading-day-a-november-5-market-bonfire-ce785fddda8ff126',
 'soxx_split':'https://www.sec.gov/Archives/edgar/data/1100663/000119312526430480/d156277d497.htm',
 'bis_policy':'https://media.bis.gov/sites/default/files/documents/DoC%20Revises%20License%20Review%20Policy%20for%20Semiconductors%20Exports.pdf',
 'nyse':'https://www.nyse.com/markets/hours-calendars',
 'nasdaq_info':'https://api.nasdaq.com/api/quote/SOXL/info?assetclass=etf',
 'nasdaq_summary':'https://api.nasdaq.com/api/quote/SOXL/summary?assetclass=etf'
}
def fetch(item):
 name,url=item
 out={'name':name,'url':url,'checked_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()}
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25)
  out.update(status=r.status_code,bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest())
  if len(r.content)>10_000_000: raise ValueError('10 MB cap')
  ext='pdf' if 'pdf' in r.headers.get('Content-Type','') else 'html'
  (DEST/f'{name}.{ext}').write_bytes(r.content)
  if ext=='html':
   soup=BeautifulSoup(r.text,'html.parser')
   for tag in soup(['script','style','nav','footer','header']):tag.decompose()
   (DEST/f'{name}.txt').write_text(soup.get_text(' ',strip=True))
 except Exception as e:out['error']=repr(e)
 return out
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(fetch,SOURCES.items()))
 (ROOT/'forecast_source_manifest.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(json.dumps(r,ensure_ascii=False,indent=2))
