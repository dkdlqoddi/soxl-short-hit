"""Frozen evidence for KORU forecast 2026-11-06; writes only beside this script."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
import json, re, requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo('Asia/Seoul')
yf.set_tz_cache_location(str(ROOT / 'yf-cache'))
def now(): return datetime.now(KST).isoformat()
def save(name, content):
    if not isinstance(content, str): content = json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False)
    assert len(content.encode()) < 10_000_000, name
    (ROOT/name).write_text(content, encoding='utf-8')
def get_history(sym, period, interval):
    name = re.sub('[^A-Za-z0-9_.-]', '_', sym)+'_'+interval
    rec = dict(symbol=sym,period=period,interval=interval,file=name+'.csv',requested_at_kst=now())
    rec['url'] = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym,safe="")}?range={period}&interval={interval}&includePrePost=true'
    try:
        f = yf.Ticker(sym).history(period=period,interval=interval,prepost=True,auto_adjust=False,actions=True,timeout=25)
        save(name+'.csv',f.to_csv(index_label='timestamp'))
        rec.update(rows=len(f),first=str(f.index[0]) if len(f) else None,last=str(f.index[-1]) if len(f) else None)
    except Exception as e: rec['error']=str(e)
    rec['retrieved_at_kst']=now()
    return rec
def get_http(name,url):
    rec=dict(file=name,url=url,requested_at_kst=now())
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25)
        rec['http_status']=r.status_code
        r.raise_for_status()
        save(name,r.text)
    except Exception as e: rec['error']=str(e)
    rec['retrieved_at_kst']=now()
    return rec
def main():
    manifest=dict(base_time_kst='2026-11-06 10:42:00+09:00',started_at_kst=now(),yfinance_version=yf.__version__,history=[],http=[])
    syms=['KORU','EWY','SOXX','MU','NVDA','SKHY','SMSN.IL','^GSPC','^IXIC','^VIX','ES=F','NQ=F','KRW=X','DX-Y.NYB','^TNX','^KS11','005930.KS','000660.KS']
    hist=[(s,'5d','1m') for s in syms]
    hist += [(s,'max' if s in ['KORU','EWY','^KS11'] else '1mo','1d') for s in syms]
    hist += [('KORU','60d','5m'),('KORU','730d','1h'),('EWY','730d','1h')]
    urls=[(f'naver_{code}_basic.json',f'https://m.stock.naver.com/api/{kind}/{code}/basic') for kind,code in [('index','KOSPI'),('stock','005930'),('stock','000660')]]
    urls += [('naver_KOSPI_trend.json','https://m.stock.naver.com/api/index/KOSPI/trend'),('nasdaq_KORU.json','https://api.nasdaq.com/api/quote/KORU/historical?assetclass=etf&fromdate=2026-11-01&todate=2026-11-05&limit=100'),('yahoo_KORU_raw.json','https://query1.finance.yahoo.com/v8/finance/chart/KORU?range=5d&interval=1m&includePrePost=true'),('ewy_holdings.csv','https://www.ishares.com/us/products/239681/ishares-msci-south-korea-etf/latest-holdings.csv'),('prekospi.html','https://www.prekospi.com/'),('mkospi.html','https://mkospi.com/')]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(get_history,*t):'history' for t in hist}
        futures.update({pool.submit(get_http,*t):'http' for t in urls})
        for fut in as_completed(futures):
            rec=fut.result(); manifest[futures[fut]].append(rec)
            print(rec['file'],rec.get('rows',rec.get('http_status')),rec.get('error',''),flush=True)
    manifest['completed_at_kst']=now();save('manifest.json',manifest)
if __name__=='__main__': main()
