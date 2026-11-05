"""복기 교훈 검증용 과거 데이터 수집 (Claude Fable Max).

- 일봉 3년: EWY, KORU, 278540.KS(KODEX MSCI Korea TR), ^KS11, KRW=X, SOXX, SPY, MU
- 1시간봉 730일: KORU(프리·애프터 포함), ^KS11, KRW=X
실행: python3 review_fetch_hist.py
"""
import os
import sys
import time

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY = ["EWY", "KORU", "278540.KS", "^KS11", "KRW=X", "SOXX", "SPY", "MU"]
HOURLY_PP = ["KORU"]
HOURLY = ["^KS11", "KRW=X"]


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
    print("fetched_at_kst", pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S"))
    for sym in DAILY:
        df = fetch(sym, period="3y", interval="1d", auto_adjust=False)
        df.to_csv(os.path.join(HERE, f"h_d1_{safe(sym)}.csv"))
        print(sym, "1d", len(df), df.index[0], df.index[-1])
    for sym in HOURLY_PP:
        df = fetch(sym, period="730d", interval="1h", prepost=True)
        df.index = df.index.tz_convert("America/New_York")
        df.to_csv(os.path.join(HERE, f"h_h1_{safe(sym)}.csv"))
        print(sym, "1h", len(df), df.index[0], df.index[-1])
    for sym in HOURLY:
        df = fetch(sym, period="730d", interval="1h")
        df.index = df.index.tz_convert("Asia/Seoul")
        df.to_csv(os.path.join(HERE, f"h_h1_{safe(sym)}.csv"))
        print(sym, "1h", len(df), df.index[0], df.index[-1])


if __name__ == "__main__":
    main()
