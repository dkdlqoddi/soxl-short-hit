"""Collect market evidence for the November 5 KORU review. All output is local."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo('Asia/Seoul')
yf.set_tz_cache_location(str(ROOT / 'yf-cache'))
SYMBOLS = ['KORU','EWY','SOXX','MU','QCOM','ARM','AMD','^GSPC','^IXIC',
           '^VIX','KRW=X','^KS11','005930.KS','000660.KS','278540.KS']

def now():
    return datetime.now(KST).isoformat()

def dump(name, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    assert len(text.encode()) < 10_000_000
    (ROOT/name).write_text(text, encoding='utf-8')

def fetch_symbol(symbol):
    out = {'symbol':symbol,'intervals':{}}
    for interval,period in [('1m','5d'),('1d','1mo')]:
        start = now()
        try:
            frame = yf.Ticker(symbol).history(period=period, interval=interval,
                prepost=True, auto_adjust=False, actions=True, timeout=25)
            name = re.sub('[^A-Za-z0-9_.-]','_',symbol)+'_'+interval+'.csv'
            frame.to_csv(ROOT/name,index_label='timestamp')
            out['intervals'][interval] = dict(file=name,rows=len(frame),
                first=str(frame.index[0]) if len(frame) else None,
                last=str(frame.index[-1]) if len(frame) else None,
                requested_at_kst=start,retrieved_at_kst=now(),
                source_url=f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={period}&interval={interval}&includePrePost=true')
        except Exception as e:
            out['intervals'][interval] = dict(error=str(e),retrieved_at_kst=now())
    return out

def main():
    manifest = dict(started_at_kst=now(),yfinance_version=yf.__version__,
                    auto_adjust=False,prepost=True,symbols=[],http=[])
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch_symbol,s) for s in SYMBOLS]):
            item=future.result()
            manifest['symbols'].append(item)
            print(item['symbol'],{k:v.get('rows',v.get('error')) for k,v in item['intervals'].items()},flush=True)
    urls = [(f'naver_{code}.json',f'https://m.stock.naver.com/api/{kind}/{code}/basic')
        for kind,code in [('index','KOSPI'),('stock','005930'),('stock','000660')]]
    urls += [('nasdaq_KORU_daily.json','https://api.nasdaq.com/api/quote/KORU/historical?assetclass=etf&fromdate=2026-11-02&todate=2026-11-05&limit=100')]
    for name,url in urls:
        rec=dict(file=name,url=url,requested_at_kst=now())
        try:
            r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'},timeout=25)
            rec['http_status']=r.status_code
            r.raise_for_status()
            dump(name,r.json())
        except Exception as e:
            rec['error']=str(e)
        rec['retrieved_at_kst']=now()
        manifest['http'].append(rec)
    manifest['completed_at_kst']=now()
    dump('collection_manifest.json',manifest)
    print('manifest',manifest['completed_at_kst'],flush=True)

if __name__=='__main__':
    main()
