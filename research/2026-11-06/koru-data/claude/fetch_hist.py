"""교훈 검증용 과거 데이터 수집 (Claude Fable Max, KORU 11/5 회차 복기).
일봉 전체: EWY, KORU, ^KS11, SPY, ^SOX, SOXX, MU, 278540.KS, KRW=X, SKHY, ^VIX
1시간봉 730일: KORU·EWY(프리·애프터 포함), ^KS11, KRW=X
원본은 hist/ 아래 pickle로만 두고(커밋 대상 아님, .gitignore 없음 → 실행 후 삭제), 통계 결과만 남긴다.
실행: python3 fetch_hist.py
"""
import sys, time
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent / "hist"
OUT.mkdir(exist_ok=True)

def fetch(sym, **kw):
    for i in range(3):
        try:
            df = yf.Ticker(sym).history(**kw)
            if len(df):
                return df
        except Exception as e:  # noqa
            print("retry", sym, e, file=sys.stderr)
        time.sleep(2 + 2 * i)
    return pd.DataFrame()

def safe(s):
    return s.replace("^", "").replace("=", "_").replace(".", "_")

print("fetched_at_kst", pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S"))
for s in ["EWY", "KORU", "^KS11", "SPY", "^SOX", "SOXX", "MU", "278540.KS", "KRW=X", "SKHY", "^VIX"]:
    df = fetch(s, period="max", interval="1d", auto_adjust=False)
    df.to_pickle(OUT / f"d_{safe(s)}.pkl")
    print(f"{s:10s} 1d rows={len(df):5d} {str(df.index[0])[:10]} → {str(df.index[-1])[:10]}")
for s in ["KORU", "EWY"]:
    df = fetch(s, period="730d", interval="1h", prepost=True, auto_adjust=False)
    df.to_pickle(OUT / f"h_{safe(s)}.pkl")
    print(f"{s:10s} 1h rows={len(df):5d} {df.index[0]} → {df.index[-1]}")
for s in ["^KS11", "KRW=X"]:
    df = fetch(s, period="730d", interval="1h", auto_adjust=False)
    df.to_pickle(OUT / f"h_{safe(s)}.pkl")
    print(f"{s:10s} 1h rows={len(df):5d} {df.index[0]} → {df.index[-1]}")
