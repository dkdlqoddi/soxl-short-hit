"""공통 로더: yfinance 1분봉 CSV를 읽어 미국 동부시간 인덱스와 KST 열을 붙인다."""
import pandas as pd

def load(sym, kind="1m"):
    fn = sym.replace("^", "").replace("=", "") + f"_{kind}.csv"
    df = pd.read_csv(fn, index_col=0)
    idx = pd.to_datetime(df.index, utc=True)
    df.index = idx.tz_convert("America/New_York")
    df["kst"] = idx.tz_convert("Asia/Seoul").strftime("%m/%d %H:%M")
    return df

def at(df, ts):
    """ts(동부시간 문자열) 시각 이하의 마지막 봉."""
    t = pd.Timestamp(ts, tz="America/New_York")
    sub = df[df.index <= t]
    return sub.iloc[-1]
