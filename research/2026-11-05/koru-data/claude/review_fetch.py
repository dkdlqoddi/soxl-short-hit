"""KORU 2026-11-04 회차 복기용 시세 수집 (Claude Fable Max).

yfinance 1분봉(프리·애프터 포함)과 일봉을 받아 CSV로 저장한다.
실행: python3 review_fetch.py   (저장 위치: 이 스크립트가 있는 폴더)
"""
import os
import sys
import time

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))

# 1분봉 (시간외 포함): KORU와 연동 자산
M1 = ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "AMD", "QCOM", "ARM", "SKHY", "SPY"]
# 1분봉 (24시간/현지장): 선물·환율·한국 지수와 종목
M1_OTHER = ["ES=F", "NQ=F", "KRW=X", "^KS11", "005930.KS", "000660.KS", "278540.KS"]
DAILY = ["KORU", "EWY", "SOXX", "SOXL", "MU", "NVDA", "AMD", "QCOM", "ARM", "SKHY", "^KS11",
         "005930.KS", "000660.KS", "278540.KS", "KRW=X", "^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX"]


def safe(sym: str) -> str:
    return sym.replace("^", "").replace("=", "_").replace(".", "_")


def fetch(sym: str, **kw) -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.Ticker(sym).history(**kw)
            if len(df):
                return df
        except Exception as e:  # noqa: BLE001
            print(f"  retry {sym}: {e}", file=sys.stderr)
        time.sleep(2 + attempt * 2)
    return pd.DataFrame()


def main() -> None:
    stamp = pd.Timestamp.now(tz="Asia/Seoul")
    print("fetched_at_kst", stamp.strftime("%Y-%m-%d %H:%M:%S"))
    rows = []
    for sym in M1:
        df = fetch(sym, period="5d", interval="1m", prepost=True)
        if df.empty:
            print("EMPTY", sym)
            continue
        df.index = df.index.tz_convert("America/New_York")
        df.to_csv(os.path.join(HERE, f"m1_{safe(sym)}.csv"))
        rows.append((sym, "1m", len(df), str(df.index[0]), str(df.index[-1]), float(df["Close"].iloc[-1])))
    for sym in M1_OTHER:
        df = fetch(sym, period="5d", interval="1m", prepost=True)
        if df.empty:
            print("EMPTY", sym)
            continue
        df.index = df.index.tz_convert("Asia/Seoul")
        df.to_csv(os.path.join(HERE, f"m1_{safe(sym)}.csv"))
        rows.append((sym, "1m", len(df), str(df.index[0]), str(df.index[-1]), float(df["Close"].iloc[-1])))
    for sym in DAILY:
        df = fetch(sym, period="3mo", interval="1d", auto_adjust=False)
        if df.empty:
            print("EMPTY", sym)
            continue
        df.to_csv(os.path.join(HERE, f"d1_{safe(sym)}.csv"))
        rows.append((sym, "1d", len(df), str(df.index[0]), str(df.index[-1]), float(df["Close"].iloc[-1])))
    out = pd.DataFrame(rows, columns=["symbol", "interval", "rows", "first", "last", "last_close"])
    out["fetched_at_kst"] = stamp.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(os.path.join(HERE, "fetch_manifest.csv"), index=False)
    print(out.to_string())


if __name__ == "__main__":
    main()
