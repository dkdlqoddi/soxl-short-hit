"""Archive public prices for this forecast; never replace an existing snapshot."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote
import hashlib
import json
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'forecast_raw'
DEST.mkdir(exist_ok=True)
KST = ZoneInfo('Asia/Seoul')
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def stamp():
    return datetime.now(KST).isoformat()

def save(path, data):
    if len(data) > 10_000_000:
        raise ValueError('10 MB cap exceeded')
    path.write_bytes(data)

def chart(task):
    symbol, period, interval = task
    slug = symbol.replace('^', '').replace('=', '_').replace('.', '_')
    stem = f'{slug}_{period}_{interval}'
    rawpath = DEST / (stem + '.json')
    if rawpath.exists():
        return {'task': task, 'cached': True, 'path': str(rawpath)}
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + quote(symbol, safe='')
    params = {'range': period, 'interval': interval, 'includePrePost': 'true', 'events': 'div,splits'}
    if period == '2010_2026':
        params.pop('range')
        params['period1'] = 1268265600
        params['period2'] = 1793923200
    started = stamp()
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=35)
        r.raise_for_status()
        js = r.json()
        obj = js['chart']['result'][0]
        raw = {'fetched_kst': stamp(), 'started_kst': started, 'url': r.url, 'data': js}
        blob = json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode()
        save(rawpath, blob)
        q = obj['indicators']['quote'][0]
        df = pd.DataFrame(q, index=pd.to_datetime(obj['timestamp'], unit='s', utc=True))
        df.index.name = 'timestamp_utc'
        df['time_et'] = df.index.tz_convert('America/New_York').astype(str)
        df['time_kst'] = df.index.tz_convert('Asia/Seoul').astype(str)
        adj = obj['indicators'].get('adjclose')
        if adj:
            df['adjclose'] = adj[0]['adjclose']
        save(DEST / (stem + '.csv'), df.to_csv().encode())
        return {'symbol': symbol, 'period': period, 'interval': interval, 'fetched_kst': raw['fetched_kst'],
                'url': r.url, 'rows': len(df), 'first': str(df.index.min()), 'last': str(df.index.max()),
                'events': obj.get('events', {}), 'sha256': hashlib.sha256(blob).hexdigest(), 'path': str(rawpath)}
    except Exception as e:
        return {'task': task, 'started_kst': started, 'error': repr(e)}

def simple(name, url):
    path = DEST / (name + '.json')
    if path.exists():
        return {'name': name, 'cached': True}
    try:
        r = requests.get(url, headers=HEADERS, timeout=35)
        r.raise_for_status()
        js = {'url': r.url, 'fetched_kst': stamp(), 'data': r.json()}
        save(path, json.dumps(js, ensure_ascii=False).encode())
        return {'name': name, 'url': r.url, 'fetched_kst': js['fetched_kst'], 'path': str(path)}
    except Exception as e:
        return {'name': name, 'url': url, 'error': repr(e)}

def main():
    syms = ['SOXL','SOXX','SMH','NVDA','AMD','AVGO','MU','TSM','ASML','QCOM','ARM',
            'QQQ','NQ=F','^VIX','^TNX','KRW=X','DX-Y.NYB','^KS11','005930.KS','000660.KS']
    tasks = [(s,'5d','1m') for s in syms]
    tasks += [(s,'1mo','1d') for s in syms]
    tasks += [('SOXL','max','1d'),('SOXX','max','1d'),('SMH','max','1d'),
              ('SOXL','60d','5m'),('SOXL','730d','1h')]
    out = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(chart,t) for t in tasks]
        for f in as_completed(futures):
            result = f.result()
            out.append(result)
            print(json.dumps({k:v for k,v in result.items() if k not in ('events','sha256','path')}, ensure_ascii=False), flush=True)
    for name,url in [('naver_kospi','https://m.stock.naver.com/api/index/KOSPI/basic'),
                     ('naver_samsung','https://m.stock.naver.com/api/stock/005930/basic'),
                     ('naver_hynix','https://m.stock.naver.com/api/stock/000660/basic'),
                     ('nasdaq_soxl','https://api.nasdaq.com/api/quote/SOXL/historical?assetclass=etf&fromdate=2010-01-01&todate=2026-11-05&limit=10000')]:
        result = simple(name,url)
        out.append(result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
    (ROOT/'forecast_collection_manifest.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
