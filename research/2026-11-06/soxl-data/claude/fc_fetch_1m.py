"""SOXL 11/6 예측용 1분봉(시간외 포함) 수집 (Claude Fable Max). 파일명 접두사 fc_ = forecast.
복기 때 받은 *_1m.csv(09:43 KST 조회)는 그대로 두고, 애프터마켓 마감(19:59 EST)까지 들어간 새 사본을 fc_1m_<sym>.csv로 저장한다."""
import sys, time, datetime as dt
import yfinance as yf
import pandas as pd

KST = dt.timezone(dt.timedelta(hours=9))
SYMS = sys.argv[1:] or ["SOXL", "SOXX", "SMH", "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM", "INTC",
                        "QQQ", "SPY", "SOXS", "NQ=F", "ES=F", "^VIX", "^TNX", "KRW=X", "SKHY", "EWY", "^KS11", "^N225",
                        "000660.KS", "005930.KS"]
rows = []
for s in SYMS:
    df = None
    for attempt in range(3):
        try:
            df = yf.Ticker(s).history(period="5d", interval="1m", prepost=True)
            if len(df):
                break
        except Exception as e:  # noqa
            print(s, "retry", e)
        time.sleep(2)
    if df is None or not len(df):
        print(s, "EMPTY"); continue
    fn = "fc_1m_" + s.replace("^", "").replace("=", "").replace(".", "_") + ".csv"
    df[["Open", "High", "Low", "Close", "Volume"]].round(4).to_csv(fn)
    last = df.iloc[-1]
    rows.append((s, len(df), str(df.index[-1]), float(last["Close"])))
    print(s, len(df), df.index[0], df.index[-1], round(float(last["Close"]), 4))
print("fetched_at_kst", dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"))
