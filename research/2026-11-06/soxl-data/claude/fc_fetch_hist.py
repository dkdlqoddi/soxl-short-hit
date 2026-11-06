"""SOXL 11/6 예측용 장기 시세 수집 (Claude Fable Max).
일봉 전체(SOXL·^SOX·SOXX·^IXIC·^GSPC·^VIX·QQQ), SOXL·SOXX 1시간봉 730일(시간외 포함), SOXL 5분봉 60일."""
import time, datetime as dt, json, urllib.request
import yfinance as yf
import pandas as pd

KST = dt.timezone(dt.timedelta(hours=9))

def get(sym, **kw):
    for attempt in range(3):
        try:
            df = yf.Ticker(sym).history(**kw)
            if len(df):
                return df
        except Exception as e:  # noqa
            print(sym, "retry", e)
        time.sleep(2)
    return pd.DataFrame()

def fn(sym, kind):
    return f"fc_{kind}_" + sym.replace("^", "").replace("=", "").replace(".", "_") + ".csv"

for s in ["SOXL", "^SOX", "SOXX", "^IXIC", "^GSPC", "^VIX", "QQQ", "^KS11", "000660.KS"]:
    d = get(s, period="max", interval="1d", auto_adjust=False)
    d.round(4).to_csv(fn(s, "1d"))
    print(s, "1d", len(d), d.index[0].date(), d.index[-1].date(), d[["Open", "High", "Low", "Close"]].tail(3).round(2).values.tolist())
for s in ["SOXL", "SOXX"]:
    h = get(s, period="730d", interval="1h", prepost=True)
    h[["Open", "High", "Low", "Close", "Volume"]].round(4).to_csv(fn(s, "1h"))
    print(s, "1h", len(h), h.index[0], h.index[-1])
m5 = get("SOXL", period="60d", interval="5m", prepost=True)
m5[["Open", "High", "Low", "Close", "Volume"]].round(4).to_csv(fn("SOXL", "5m"))
print("SOXL 5m", len(m5), m5.index[0], m5.index[-1])
print("splits SOXL", yf.Ticker("SOXL").splits.tail(5).to_dict())
print("splits SOXX", yf.Ticker("SOXX").splits.tail(5).to_dict())

# Nasdaq 일봉 API (공식 종가 교차 확인)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
try:
    url = "https://api.nasdaq.com/api/quote/SOXL/historical?assetclass=etf&fromdate=2026-10-01&todate=2026-11-06&limit=100"
    j = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())
    rows = j["data"]["tradesTable"]["rows"][:6]
    json.dump(j, open("fc_nasdaq_soxl_recent.json", "w"))
    for r in rows:
        print("nasdaq", r)
except Exception as e:  # noqa
    print("nasdaq ERR", e)
print("fetched_at_kst", dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"))
