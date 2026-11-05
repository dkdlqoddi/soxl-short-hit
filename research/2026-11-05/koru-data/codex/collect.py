"""Read-only market collection for the 2026-11-04 KORU forecast review.

All artifacts stay beside this script. No adjusted intraday/overnight prices,
no invented ticks, and no other models' current-day notes are consumed.
"""
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
SYMBOLS = ['KORU', 'EWY', 'SOXX', 'MU', 'AMD', 'QCOM', 'ARM', '^GSPC',
           '^IXIC', '^VIX', 'KRW=X', '^KS11', '005930.KS', '000660.KS']

def now():
    return datetime.now(KST).isoformat()

def collect_symbol(symbol):
    item = {'symbol': symbol, 'started_at_kst': now(), 'intervals': {}}
    for interval, period in [('1m', '5d'), ('1d', '1mo')]:
        try:
            data = yf.Ticker(symbol).history(period=period, interval=interval,
                 prepost=True, auto_adjust=False, actions=False, timeout=25)
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', symbol) + '_' + interval + '.csv'
            data.to_csv(ROOT / name, index_label='timestamp')
            item['intervals'][interval] = {
                'file': name, 'rows': len(data), 'period': period,
                'first': str(data.index[0]) if len(data) else None,
                'last': str(data.index[-1]) if len(data) else None,
                'retrieved_at_kst': now(), 'bytes': (ROOT / name).stat().st_size,
                'url': 'https://query1.finance.yahoo.com/v8/finance/chart/' + symbol,
            }
        except Exception as exc:
            item['intervals'][interval] = {'error': repr(exc), 'retrieved_at_kst': now()}
    return item

def main():
    manifest = {'started_at_kst': now(), 'yfinance_version': yf.__version__,
                'auto_adjust': False, 'prepost': True, 'symbols': [], 'naver': []}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(collect_symbol, s) for s in SYMBOLS]
        for f in as_completed(futures):
            item = f.result()
            manifest['symbols'].append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
    for kind, code in [('index', 'KOSPI'), ('stock', '005930'), ('stock', '000660')]:
        url = f'https://m.stock.naver.com/api/{kind}/{code}/basic'
        rec = {'url': url, 'retrieved_at_kst': now()}
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            name = f'naver_{code}.json'
            (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
            rec.update(file=name, bytes=(ROOT/name).stat().st_size)
        except Exception as exc:
            rec['error'] = repr(exc)
        manifest['naver'].append(rec)
    manifest['completed_at_kst'] = now()
    (ROOT / 'collection_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    assert all(p.stat().st_size < 10_000_000 for p in ROOT.iterdir() if p.is_file())

if __name__ == '__main__':
    main()
