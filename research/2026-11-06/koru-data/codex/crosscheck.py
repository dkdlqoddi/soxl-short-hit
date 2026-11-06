"""Supplemental, read-only source access; keep responses and access times."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import requests

ROOT=Path(__file__).resolve().parent
def now(): return datetime.now(ZoneInfo('Asia/Seoul')).isoformat()
URLS={
 'naver_KOSPI_daily.json':'https://m.stock.naver.com/api/index/KOSPI/price?pageSize=10',
 'naver_005930_daily.json':'https://m.stock.naver.com/api/stock/005930/price?pageSize=10',
 'naver_000660_daily.json':'https://m.stock.naver.com/api/stock/000660/price?pageSize=10',
 'yahoo_KORU_1m_raw.json':'https://query1.finance.yahoo.com/v8/finance/chart/KORU?range=5d&interval=1m&includePrePost=true',
 'nasdaq_KORU_info.json':'https://api.nasdaq.com/api/quote/KORU/info?assetclass=etf',
 'korea_close_asiae.html':'https://www.asiae.co.kr/article/2026110515540205579',
 'korea_close_seoulfn.html':'https://www.seoulfn.com/news/articleView.html?idxno=642052',
 'reuters_ai_rout.html':'https://ca.investing.com/news/stock-market-news/techstock-rout-accelerates-retreat-from-the-ai-trade-4935818',
 'us_live_yahoo.html':'https://finance.yahoo.com/markets/live/stock-market-today-thursday-november-5-dow-sp-500-nasdaq-plunge-chip-stocks-melt-down-193726491.html',
 'night_futures.html':'https://www.prekospi.com/',
 'soxx_split_sec.html':'https://www.sec.gov/Archives/edgar/data/1100663/000119312526430480/d156277d497.htm',
 'productivity_bls.html':'https://www.bls.gov/news.release/archives/prod2_11052026.htm',
 'claims_dol.pdf':'https://www.dol.gov/ui/data.pdf',
}
def fetch(item):
 name,url=item; rec=dict(file=name,url=url,requested_at_kst=now())
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'*/*'},timeout=20)
  rec['http_status']=r.status_code; r.raise_for_status()
  if len(r.content)>=10_000_000: raise ValueError('response exceeds file limit')
  (ROOT/name).write_bytes(r.content)
  rec.update(bytes=len(r.content),content_type=r.headers.get('Content-Type'))
 except Exception as e: rec['error']=str(e)
 rec['retrieved_at_kst']=now()
 return rec
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=4) as pool: out=list(pool.map(fetch,URLS.items()))
 (ROOT/'crosscheck_manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 for x in out: print(x['file'],x.get('http_status'),x.get('error','OK'))
