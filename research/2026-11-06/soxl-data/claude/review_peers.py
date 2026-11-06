"""동종 종목·지수의 11/3~11/5 공식 일봉 등락과 아시아 반도체 종가, 추가 통계(2시간 종가 이후 잔여 수익률, 프리마켓 연속성 재확인).
출력: review_peers.json, peers_daily.csv"""
import json, time
import pandas as pd, numpy as np
import yfinance as yf

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
out = {}
syms = ["SOXL", "SOXS", "SOXX", "SMH", "NVDA", "AMD", "AVGO", "MU", "TSM", "ASML", "QCOM", "ARM", "INTC", "MRVL", "SNDK", "CRWV", "AAPL",
        "QQQ", "SPY", "DIA", "^GSPC", "^IXIC", "^DJI", "^NDX", "^SOX", "^VIX", "^TNX", "NQ=F", "CL=F",
        "^KS11", "000660.KS", "005930.KS", "^N225", "6857.T", "8035.T", "6146.T", "6920.T", "SKHY", "EWY", "KORU"]
rows = []
for s in syms:
    df = None
    for _ in range(3):
        try:
            df = yf.Ticker(s).history(period="1mo", interval="1d", auto_adjust=False)
            if len(df):
                break
        except Exception as e:  # noqa
            print(s, "retry", e)
        time.sleep(1.5)
    if df is None or not len(df):
        print(s, "EMPTY"); continue
    df.index = df.index.strftime("%Y-%m-%d")
    c = df["Close"].copy(); o = df["Open"].copy()
    if s == "SOXX":                                   # 11/2~11/4 분할 미조정분 보정 (3대1, 11/5 발효)
        for k in ("2026-11-02", "2026-11-03", "2026-11-04"):
            if c.get(k, 0) > 400:
                c[k] /= 3; o[k] /= 3
    r = {"sym": s}
    for k in ("2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"):
        r["c" + k[-5:]] = round(float(c[k]), 3) if k in c.index and pd.notna(c[k]) else None
        r["o" + k[-5:]] = round(float(o[k]), 3) if k in o.index and pd.notna(o[k]) else None
    def chg(a, b):
        return round((b / a - 1) * 100, 2) if a and b else None
    r["d1104"] = chg(r["c11-03"], r["c11-04"]); r["d1105"] = chg(r["c11-04"], r["c11-05"])
    r["oo"] = chg(r["o11-04"], r["o11-05"]); r["gap1105"] = chg(r["c11-04"], r["o11-05"]); r["oc1105"] = chg(r["o11-05"], r["c11-05"])
    r["two_day"] = chg(r["c11-03"], r["c11-05"])
    rows.append(r)
p = pd.DataFrame(rows).set_index("sym")
p.to_csv("peers_daily.csv")
print(p[["c11-03", "o11-04", "c11-04", "d1104", "o11-05", "c11-05", "d1105", "gap1105", "oo", "oc1105", "two_day"]].to_string())
out["peers"] = p.where(pd.notna(p), None).to_dict(orient="index")

# ── 추가 통계
NY = "America/New_York"
def rd(fn):
    df = pd.read_csv(fn, index_col=0); df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY); return df
def stat(x):
    x = pd.Series(x).dropna()
    return dict(N=int(len(x)), up=round(float((x > 0).mean() * 100), 1), mean=round(float(x.mean() * 100), 2), med=round(float(x.median() * 100), 2),
                q25=round(float(x.quantile(.25) * 100), 1), q75=round(float(x.quantile(.75) * 100), 1)) if len(x) else dict(N=0)
d = rd("SOXL_1d.csv"); d.index = d.index.normalize().tz_localize(None)
d["pc"] = d["Close"].shift(1); d["gap"] = d["Open"] / d["pc"] - 1; d["oo"] = d["Open"].shift(-1) / d["Open"] - 1; d["oc"] = d["Close"] / d["Open"] - 1
h = rd("SOXL_1h.csv"); hm = h.index.hour * 100 + h.index.minute
def at(code, col):
    x = h[hm == code][col].copy(); x.index = x.index.normalize().tz_localize(None); return x
t = pd.DataFrame({"o": at(930, "Open"), "c1": at(930, "Close"), "c2": at(1030, "Close"), "pm4o": at(400, "Open"), "pm4c": at(400, "Close")}).join(d[["pc", "gap", "oo", "oc", "Close"]], how="inner")
t["r1"] = t["c1"] / t["o"] - 1; t["r2"] = t["c2"] / t["o"] - 1
t["rest1"] = (1 + t["oo"]) / (1 + t["r1"]) - 1; t["rest2"] = (1 + t["oo"]) / (1 + t["r2"]) - 1
t["c2_to_close"] = t["Close"] / t["c2"] - 1
th = t.loc[:"2026-11-03"]; gd = th[th["gap"] <= -0.03]
e = {}
e["rest2 | gap<=-3 & r2<=-3"] = stat(gd.loc[gd["r2"] <= -0.03, "rest2"])
e["rest2 | gap<=-3 & r2<0"] = stat(gd.loc[gd["r2"] < 0, "rest2"])
e["rest2 | gap<=-3 & r2>=+1.5"] = stat(gd.loc[gd["r2"] >= 0.015, "rest2"])
e["c2→close | gap<=-3 & r2<=-3"] = stat(gd.loc[gd["r2"] <= -0.03, "c2_to_close"])
e["rest1 | gap<=-3 & r1<0"] = stat(gd.loc[gd["r1"] < 0, "rest1"])
e["rest1 | gap<=-3 & r1>=+1.5"] = stat(gd.loc[gd["r1"] >= 0.015, "rest1"])
e["oo | gap<=-3 & -3<r2<0"] = stat(gd.loc[(gd["r2"] > -0.03) & (gd["r2"] < 0), "oo"])
e["oo | gap<=-3 & 0<=r2<1.5"] = stat(gd.loc[(gd["r2"] >= 0) & (gd["r2"] < 0.015), "oo"])
# 노트 작성 당시 창(최근 2년: 2024-11-05~)으로 재현
g2 = gd.loc["2024-11-05":]; t2 = th.loc["2024-11-05":]
e["[2y] days"] = dict(N=int(len(t2)))
e["[2y] gap<=-3"] = stat(g2["oo"]); e["[2y] gap<=-3 & r1>=+1.5"] = stat(g2.loc[g2["r1"] >= 0.015, "oo"]); e["[2y] gap<=-3 & r1<0"] = stat(g2.loc[g2["r1"] < 0, "oo"])
e["[2y] gap<=-3 & 0<=r1<1.5"] = stat(g2.loc[(g2["r1"] >= 0) & (g2["r1"] < 0.015), "oo"])
e["[2y] gap<=-3 & r2<=-3"] = stat(g2.loc[g2["r2"] <= -0.03, "oo"]); e["[2y] gap<=-3 & r2<0"] = stat(g2.loc[g2["r2"] < 0, "oo"])
# 프리마켓 연속성: 05:00 ET(04:00 봉 종가) 기준으로 재확인
tt = t.loc[:"2026-11-04"].dropna(subset=["pm4c"])
tt["g5"] = tt["pm4c"] / tt["pc"] - 1; tt["run5"] = tt["o"] / tt["pm4c"] - 1
e["run5 | 05:00 gap<=-5"] = stat(tt.loc[tt["g5"] <= -0.05, "run5"]); e["run5 | 05:00 gap<=-3"] = stat(tt.loc[tt["g5"] <= -0.03, "run5"])
e["run5 | 05:00 gap>=+5"] = stat(tt.loc[tt["g5"] >= 0.05, "run5"]); e["run5 | all"] = stat(tt["run5"])
e["oc | 05:00 gap<=-5"] = stat(tt.loc[tt["g5"] <= -0.05, "oc"])
out["extra"] = e
print(pd.DataFrame(e).T.to_string())
print("11/5:", "05:00 gap", round(float(t.loc["2026-11-05", "pm4c"] / t.loc["2026-11-05", "pc"] - 1) * 100, 2), "run5", round(float(t.loc["2026-11-05", "o"] / t.loc["2026-11-05", "pm4c"] - 1) * 100, 2))
print("11/4 r2 bucket members (gap<=-3 & r2<=-3):"); print(gd.loc[gd["r2"] <= -0.03, ["gap", "r1", "r2", "oc", "oo"]].round(4).tail(15).to_string())
json.dump(out, open("review_peers.json", "w"), ensure_ascii=False, indent=1, default=str)
