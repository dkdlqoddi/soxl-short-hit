"""2.4절 연동 자산 표: 공식 일봉(review_peers.py가 저장한 peers_daily.csv)의 11/3·11/4 종가와 11/5 시가에
1분봉의 11/4 시간외 마지막 가격과 11/5 15:59 종가를 붙인다. 조회 시점에 야후 일봉의 11/5 종가가 비어 있어
SOXL·SOXX만 09:44 KST에 받은 일봉 종가를 쓰고 나머지는 1분봉 15:59 종가를 쓴다. 출력: peers_final.csv/json"""
import json
import pandas as pd
from load import load

T = lambda x: pd.Timestamp(x, tz="America/New_York")
off = pd.read_csv("peers_daily.csv", index_col=0)
daily_close = {}
for s in ("SOXL", "SOXX"):
    d = pd.read_csv(f"{s}_1d.csv", index_col=0)
    assert d.index[-1].startswith("2026-11-05")
    daily_close[s] = float(d["Close"].iloc[-1])
rows = {}
for s in ["SOXL", "SOXX", "SMH", "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM"]:
    df = load(s)
    r5 = df[(df.index >= T("2026-11-05 09:30")) & (df.index < T("2026-11-05 16:00"))]
    c5 = daily_close.get(s, float(r5["Close"].iloc[-1]))
    c3, o4, c4, o5 = (float(off.loc[s, k]) for k in ("c11-03", "o11-04", "c11-04", "o11-05"))
    ah4 = float(df[df.index <= T("2026-11-04 19:59")]["Close"].iloc[-1])
    rows[s] = dict(c1103=c3, c1104=c4, d1104=round((c4 / c3 - 1) * 100, 2), ah1104=round((ah4 / c4 - 1) * 100, 2), o1105=o5,
                   gap1105=round((o5 / c4 - 1) * 100, 2), oo=round((o5 / o4 - 1) * 100, 2), c1105=round(c5, 3),
                   src=("일봉" if s in daily_close else "1분봉 15:59"), d1105=round((c5 / c4 - 1) * 100, 2), oc1105=round((c5 / o5 - 1) * 100, 2))
p = pd.DataFrame(rows).T
p.to_csv("peers_final.csv")
json.dump(rows, open("peers_final.json", "w"), indent=1, ensure_ascii=False)
print(p.to_string())
