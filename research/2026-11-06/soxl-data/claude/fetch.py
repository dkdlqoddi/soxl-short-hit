"""SOXL 11/5 회차 복기용 시세 수집 (Claude Fable Max).
1분봉(시간외 포함) 5일치, SOXL 1시간봉, 일봉을 저장한다. 인덱스는 미국 동부시간."""
import sys, time, datetime as dt
import yfinance as yf
import pandas as pd

# 처음에는 INTC·MRVL·QQQ·SPY·DIA·NQ=F·^VIX·^TNX·SOXS까지 20종을 받아 훑어봤고, 노트 수치에 쓴 11종만 남겼다.
SYMS_1M = ["SOXL", "SOXX", "SMH", "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM"]
out = {}
for s in SYMS_1M:
    for attempt in range(3):
        try:
            df = yf.Ticker(s).history(period="5d", interval="1m", prepost=True)
            if len(df):
                break
        except Exception as e:  # noqa
            print(s, "retry", e)
        time.sleep(2)
    fn = s.replace("^", "").replace("=", "") + "_1m.csv"
    df.to_csv(fn)
    out[s] = (len(df), str(df.index[0]) if len(df) else None, str(df.index[-1]) if len(df) else None)
    print(s, out[s])

for s in ["SOXL", "SOXX", "SPY"]:
    d = yf.Ticker(s).history(period="max", interval="1d", auto_adjust=False)
    d.to_csv(s + "_1d.csv")
    print(s, "1d", len(d), d.index[-1])
h = yf.Ticker("SOXL").history(period="730d", interval="1h", prepost=True)
h.to_csv("SOXL_1h.csv")
print("SOXL 1h", len(h), h.index[0], h.index[-1])
print("fetched_at_kst", dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"))
