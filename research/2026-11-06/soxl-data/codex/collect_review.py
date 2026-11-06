"""Capture immutable review inputs; all artifacts stay beside this script."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import requests
import pandas as pd

OUT = Path(__file__).resolve().parent
KST = ZoneInfo('Asia/Seoul')
SYMBOLS = ['SOXL', 'SOXX', 'SMH', 'NVDA', 'AMD', 'AVGO', 'MU', 'TSM',
           'ASML', 'QCOM', 'ARM', 'QQQ', 'NQ=F', '^VIX', '^TNX']

def key(symbol):
    return symbol.replace('^', '').replace('=', '_')

def fetch(spec):
    symbol, interval, window = spec
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
    params = {'range': window, 'interval': interval, 'includePrePost': 'true',
              'events': 'div,splits'}
    started = datetime.now(KST).isoformat()
    response = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=45)
    response.raise_for_status()
    data = response.json()
    result = data['chart']['result'][0]
    quote = result['indicators']['quote'][0]
    frame = pd.DataFrame(quote, index=pd.to_datetime(result['timestamp'], unit='s', utc=True))
    frame.index = frame.index.tz_convert('America/New_York')
    frame.index.name = 'bar_start_et'
    frame.insert(0, 'bar_start_kst', frame.index.tz_convert('Asia/Seoul'))
    raw = {'symbol': symbol, 'interval': interval, 'request_url': response.url,
           'started_at_kst': started, 'checked_at_kst': datetime.now(KST).isoformat(),
           'response': data}
    return spec, raw, frame

def main():
    specs = [(s, '1m', '5d') for s in SYMBOLS] + [(s, '1d', '1mo') for s in SYMBOLS]
    manifest = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [(s, pool.submit(fetch, s)) for s in specs]
        for spec, future in futures:
            symbol, interval, _ = spec
            try:
                _, raw, frame = future.result()
                stem = f'{key(symbol)}_{interval}'
                rawpath = OUT / f'{stem}_raw.json'
                payload = json.dumps(raw, ensure_ascii=False, separators=(',', ':')).encode()
                assert len(payload) < 10_000_000
                rawpath.write_bytes(payload)
                frame.to_csv(OUT / f'{stem}.csv')
                entry = {k: raw[k] for k in ['symbol', 'interval', 'request_url', 'checked_at_kst']}
                entry.update({'rows': len(frame), 'first': str(frame.index.min()),
                              'last': str(frame.index.max()), 'raw_file': rawpath.name,
                              'sha256': hashlib.sha256(payload).hexdigest()})
                print(symbol, interval, len(frame), entry['last'], flush=True)
            except Exception as exc:
                entry = {'symbol': symbol, 'interval': interval, 'error': str(exc),
                         'checked_at_kst': datetime.now(KST).isoformat()}
                print('ERROR', symbol, interval, str(exc), flush=True)
            manifest.append(entry)
    (OUT / 'collection_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    main()
