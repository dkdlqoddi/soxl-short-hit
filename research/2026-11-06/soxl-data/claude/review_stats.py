"""복기용 통계: 첫 1시간 버킷 재현·세분화, 꼬리 빈도, 급락장 레짐, 업종 이탈, 변동성 대비 범위.
입력: SOXL_1h.csv(2년, 시간외 포함), SOXL_1d.csv, SOXX_1d.csv, SPY_1d.csv. 출력: review_stats.json"""
import json
import pandas as pd, numpy as np

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
NY = "America/New_York"
out = {}

def rd(fn):
    df = pd.read_csv(fn, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY)
    return df

def stat(x, label=None):
    x = pd.Series(x).dropna()
    if not len(x):
        return dict(N=0)
    return dict(N=int(len(x)), up=round(float((x > 0).mean() * 100), 1), mean=round(float(x.mean() * 100), 2), med=round(float(x.median() * 100), 2),
                q25=round(float(x.quantile(.25) * 100), 1), q75=round(float(x.quantile(.75) * 100), 1),
                le10=round(float((x <= -0.10).mean() * 100), 1), le15=round(float((x <= -0.15).mean() * 100), 1), ge10=round(float((x >= 0.10).mean() * 100), 1),
                min=round(float(x.min() * 100), 1), max=round(float(x.max() * 100), 1))

# ── 일봉 테이블
d = rd("SOXL_1d.csv"); d.index = d.index.normalize().tz_localize(None)
d["pc"] = d["Close"].shift(1)
d["gap"] = d["Open"] / d["pc"] - 1
d["oc"] = d["Close"] / d["Open"] - 1
d["oo"] = d["Open"].shift(-1) / d["Open"] - 1
d["co"] = d["Open"].shift(-1) / d["Close"] - 1            # 종가 → 다음 시가
d["ret"] = d["Close"] / d["pc"] - 1
d["prev_ret"] = d["ret"].shift(1)
d["max20c"] = d["Close"].rolling(20).max().shift(1)       # 전일까지 20일 최고 종가
d["dd20"] = d["pc"] / d["max20c"] - 1
tr = pd.concat([d["High"] - d["Low"], (d["High"] - d["pc"]).abs(), (d["Low"] - d["pc"]).abs()], axis=1).max(axis=1)
d["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
d["atrp"] = (d["atr14"] / d["Close"]).shift(1)            # 전일 마감 기준 ATR%
d["oo_sd20"] = d["oo"].shift(1).rolling(20).std()         # 전일 시가까지 확정된 최근 20개 O→O' 표준편차
d["range"] = (d["High"] - d["Low"]) / d["Open"]
d["clv"] = (d["Close"] - d["Low"]) / (d["High"] - d["Low"])
print(d.loc["2026-10-26":, ["Open", "High", "Low", "Close", "gap", "oc", "oo", "co", "ret", "dd20", "atrp", "oo_sd20", "clv"]].round(4).to_string())
D4 = pd.Timestamp("2026-11-04"); D5 = pd.Timestamp("2026-11-05")
out["day_1104"] = {k: round(float(d.loc[D4, k]), 4) for k in ("gap", "oc", "oo", "co", "ret", "prev_ret", "dd20", "atrp", "oo_sd20", "clv", "range")}
out["day_1105"] = {k: round(float(d.loc[D5, k]), 4) for k in ("gap", "oc", "ret", "dd20", "atrp", "oo_sd20", "clv", "range")}
out["z_oo_1104"] = round(float(d.loc[D4, "oo"] / d.loc[D4, "oo_sd20"]), 2)

hist = d.loc[:"2026-11-03"]                               # 예측 시점에 쓸 수 있던 표본 (11/3 O→O'까지)
allx = d.loc[:"2026-11-04"]                               # 11/4 결과 포함
# 순위
oo_all = allx["oo"].dropna()
out["oo_rank"] = dict(N=int(len(oo_all)), rank_from_worst=int((oo_all <= d.loc[D4, "oo"]).sum()), pct=round(float((oo_all <= d.loc[D4, "oo"]).mean() * 100), 2),
                      worst5=[(str(i.date()), round(float(v) * 100, 1)) for i, v in oo_all.nsmallest(8).items()])
ret_all = d["ret"].dropna()
out["ret_rank_1105"] = dict(N=int(len(ret_all)), rank_from_worst=int((ret_all <= d.loc[D5, "ret"]).sum()),
                            worst8=[(str(i.date()), round(float(v) * 100, 1)) for i, v in ret_all.nsmallest(8).items()])
print("oo_rank", out["oo_rank"]); print("ret_rank", out["ret_rank_1105"])

# ── 10년 일봉 버킷: 노트 재현 + 11/4 포함 + 꼬리
def buckets(df):
    b = {}
    b["all"] = stat(df["oo"])
    b["gap<=-3"] = stat(df.loc[df["gap"] <= -0.03, "oo"])
    b["gap<=-3 & prev>=+5"] = stat(df.loc[(df["gap"] <= -0.03) & (df["prev_ret"] >= 0.05), "oo"])
    b["gap<=-3 & prev>=+3 & dd20<=-30"] = stat(df.loc[(df["gap"] <= -0.03) & (df["prev_ret"] >= 0.03) & (df["dd20"] <= -0.30), "oo"])
    b["gap<=-3 & dd20<=-40"] = stat(df.loc[(df["gap"] <= -0.03) & (df["dd20"] <= -0.40), "oo"])
    b["dd20<=-40 & gap<=-2"] = stat(df.loc[(df["gap"] <= -0.02) & (df["dd20"] <= -0.40), "oo"])
    b["dd20<=-40"] = stat(df.loc[df["dd20"] <= -0.40, "oo"])
    b["dd20<=-50"] = stat(df.loc[df["dd20"] <= -0.50, "oo"])
    b["atrp>=12 & gap<=-3"] = stat(df.loc[(df["atrp"] >= 0.12) & (df["gap"] <= -0.03), "oo"])
    b["atrp>=15"] = stat(df.loc[df["atrp"] >= 0.15, "oo"])
    b["atrp>=12"] = stat(df.loc[df["atrp"] >= 0.12, "oo"])
    b["crash since 10/8"] = stat(df.loc["2026-10-08":, "oo"])
    b["crash since 10/8 overnight(co)"] = stat(df.loc["2026-10-08":, "co"])
    return b
out["daily_hist"] = buckets(hist.iloc[:-0] if False else hist.loc[:"2026-11-03"].assign(oo=lambda x: x["oo"].where(x.index < "2026-11-04")))
out["daily_incl_1104"] = buckets(allx.assign(oo=lambda x: x["oo"].where(x.index <= "2026-11-04")))
print("\n== 10y daily buckets (as of note: through 11/3 open→11/4 open)")
print(pd.DataFrame(out["daily_hist"]).T.to_string())
print("\n== incl. 11/4")
print(pd.DataFrame(out["daily_incl_1104"]).T.to_string())

# 변동성 대비 표준화 수익률의 꼬리 (전체 10년): |z| >= 2 빈도
z = (d["oo"] / d["oo_sd20"]).loc[:"2026-11-04"].dropna()
out["z_tail"] = dict(N=int(len(z)), le_m2=round(float((z <= -2).mean() * 100), 2), ge_p2=round(float((z >= 2).mean() * 100), 2),
                     le_m1_5=round(float((z <= -1.5).mean() * 100), 2), ge_p1_5=round(float((z >= 1.5).mean() * 100), 2),
                     q025=round(float(z.quantile(.025)), 2), q05=round(float(z.quantile(.05)), 2), q95=round(float(z.quantile(.95)), 2), q975=round(float(z.quantile(.975)), 2))
zh = z[d["atrp"].reindex(z.index) >= 0.12]
out["z_tail_atr12"] = dict(N=int(len(zh)), le_m2=round(float((zh <= -2).mean() * 100), 2), ge_p2=round(float((zh >= 2).mean() * 100), 2),
                           q025=round(float(zh.quantile(.025)), 2), q05=round(float(zh.quantile(.05)), 2), q95=round(float(zh.quantile(.95)), 2), q975=round(float(zh.quantile(.975)), 2))
print("z_tail", out["z_tail"]); print("z_tail_atr12", out["z_tail_atr12"])

# ── 2년 1시간봉: 첫 1시간
h = rd("SOXL_1h.csv")
f = h[(h.index.hour == 9) & (h.index.minute == 30)].copy()
f.index = f.index.normalize().tz_localize(None)
g = h[(h.index.hour == 10) & (h.index.minute == 30)].copy(); g.index = g.index.normalize().tz_localize(None)
t = pd.DataFrame({"o": f["Open"], "c1": f["Close"], "h1": f["High"], "l1": f["Low"], "c2": g["Close"]})
t = t.join(d[["pc", "Open", "Close", "gap", "oo", "oc", "prev_ret", "dd20", "atrp"]], how="inner")
t["r1"] = t["c1"] / t["o"] - 1
t["r2"] = t["c2"] / t["o"] - 1
t["rng1"] = (t["h1"] - t["l1"]) / t["o"]
t["low1"] = t["l1"] / t["o"] - 1
t["rest"] = (1 + t["oo"]) / (1 + t["r1"]) - 1             # 첫 1시간 종가 → 다음 시가
t["odiff"] = (t["o"] / t["Open"] - 1).abs()
print("\nhourly days", len(t), t.index[0], t.index[-1], "open mismatch >0.5%:", int((t["odiff"] > 0.005).sum()))
print(t.loc["2026-10-08":, ["o", "c1", "c2", "gap", "r1", "r2", "rng1", "oc", "oo"]].round(4).to_string())
out["first_hour_1104"] = {k: round(float(t.loc[D4, k]), 4) for k in ("o", "c1", "c2", "gap", "r1", "r2", "rng1", "low1", "oc", "oo", "rest")}
out["first_hour_1105"] = {k: round(float(t.loc[D5, k]), 4) for k in ("o", "c1", "c2", "gap", "r1", "r2", "rng1", "low1", "oc")}

def hb(df):
    gd = df[df["gap"] <= -0.03]
    b = {}
    b["all"] = stat(df["oo"])
    b["gap<=-3"] = stat(gd["oo"])
    b["gap<=-3 & r1>=+1.5"] = stat(gd.loc[gd["r1"] >= 0.015, "oo"])
    b["gap<=-3 & 0<=r1<+1.5"] = stat(gd.loc[(gd["r1"] >= 0) & (gd["r1"] < 0.015), "oo"])
    b["gap<=-3 & r1<0"] = stat(gd.loc[gd["r1"] < 0, "oo"])
    b["gap<=-3 & |r1|<0.5 (flat)"] = stat(gd.loc[gd["r1"].abs() < 0.005, "oo"])
    b["gap<=-3 & |r1|<1.0 (flat)"] = stat(gd.loc[gd["r1"].abs() < 0.010, "oo"])
    b["gap<=-3 & r1<=-1.0"] = stat(gd.loc[gd["r1"] <= -0.010, "oo"])
    b["gap<=-3 & r1>=+1.0"] = stat(gd.loc[gd["r1"] >= 0.010, "oo"])
    b["rng1>=8"] = stat(df.loc[df["rng1"] >= 0.08, "oo"])
    b["rng1>=8 & r1>0"] = stat(df.loc[(df["rng1"] >= 0.08) & (df["r1"] > 0), "oo"])
    b["rng1>=8 & r1<=0"] = stat(df.loc[(df["rng1"] >= 0.08) & (df["r1"] <= 0), "oo"])
    b["rng1>=8 & |r1|<1.0"] = stat(df.loc[(df["rng1"] >= 0.08) & (df["r1"].abs() < 0.01), "oo"])
    b["low1<=-3 & r1>0 (V)"] = stat(df.loc[(df["low1"] <= -0.03) & (df["r1"] > 0), "oo"])
    b["dd20<=-30 & r1>=0"] = stat(df.loc[(df["dd20"] <= -0.30) & (df["r1"] >= 0), "oo"])
    b["dd20<=-30 & r1<0"] = stat(df.loc[(df["dd20"] <= -0.30) & (df["r1"] < 0), "oo"])
    # 첫 2시간(11:30 ET) 기준
    b["gap<=-3 & r2>=+1.5"] = stat(gd.loc[gd["r2"] >= 0.015, "oo"])
    b["gap<=-3 & r2<0"] = stat(gd.loc[gd["r2"] < 0, "oo"])
    b["gap<=-3 & r2<=-3"] = stat(gd.loc[gd["r2"] <= -0.03, "oo"])
    b["gap<=-3 & |r1|<1.0 & r2<0"] = stat(gd.loc[(gd["r1"].abs() < 0.01) & (gd["r2"] < 0), "oo"])
    b["gap<=-3 & |r1|<1.0 & r2>=0"] = stat(gd.loc[(gd["r1"].abs() < 0.01) & (gd["r2"] >= 0), "oo"])
    # 같은 버킷의 O→C
    b["OC | gap<=-3 & r1<0"] = stat(gd.loc[gd["r1"] < 0, "oc"])
    b["OC | gap<=-3 & r1>=+1.5"] = stat(gd.loc[gd["r1"] >= 0.015, "oc"])
    b["OC | gap<=-3 & r2<0"] = stat(gd.loc[gd["r2"] < 0, "oc"])
    return b
th = t.loc[:"2026-11-03"]                                  # 노트 작성 시점 표본
out["hourly_hist"] = hb(th)
out["hourly_incl_1104"] = hb(t.loc[:"2026-11-04"])
print("\n== 2y hourly buckets (through 11/3)")
print(pd.DataFrame(out["hourly_hist"]).T.to_string())
print("\n== incl. 11/4")
print(pd.DataFrame(out["hourly_incl_1104"]).T.to_string())
gd = th[th["gap"] <= -0.03]
print("\nflat first hour (|r1|<1%) on gap<=-3% days:")
print(gd.loc[gd["r1"].abs() < 0.01, ["gap", "r1", "r2", "oc", "oo"]].round(4).to_string())

# ── 업종 이탈: SPY 급등 & SOXX 급락 (SOXX 상장 2001-07~)
sx = rd("SOXX_1d.csv"); sp = rd("SPY_1d.csv")
for df in (sx, sp):
    df.index = df.index.normalize().tz_localize(None)
# yfinance 일봉은 11/5 SOXX 3대1 분할을 10/30 이전에만 반영하고 11/2~11/4는 분할 전 가격으로 남겨 두었다 → 직접 보정
fix = (sx.index >= "2026-11-02") & (sx.index <= "2026-11-04")
assert sx.loc[fix, "Close"].min() > 400, "SOXX 분할 보정 대상이 이미 조정됨"
sx.loc[fix, ["Open", "High", "Low", "Close", "Adj Close"]] /= 3
m = pd.DataFrame({"soxx": sx["Close"].pct_change(), "spy": sp["Close"].pct_change()}).dropna()
m["soxx_next"] = m["soxx"].shift(-1); m["spy_next"] = m["spy"].shift(-1)
m = m.join(d[["co", "oo", "ret"]].rename(columns={"ret": "soxl"}))
m["soxl_next"] = m["soxl"].shift(-1)
print("\nSOXX/SPY 11/3~11/5:"); print(m.loc["2026-11-02":, ["soxx", "spy"]].round(4).to_string())
div = {}
mh = m.loc[:"2026-11-03"]
for nm, cond in {"spy>=+1 & soxx<=0": (mh["spy"] >= 0.01) & (mh["soxx"] <= 0),
                 "spy>=+1 & soxx<=-1": (mh["spy"] >= 0.01) & (mh["soxx"] <= -0.01),
                 "spy>=+1 & soxx<=-2": (mh["spy"] >= 0.01) & (mh["soxx"] <= -0.02),
                 "spy>=+0.5 & soxx<=-2": (mh["spy"] >= 0.005) & (mh["soxx"] <= -0.02),
                 "spy>=0 & soxx<=-3": (mh["spy"] >= 0.0) & (mh["soxx"] <= -0.03),
                 "soxx-spy<=-4pp": (mh["soxx"] - mh["spy"] <= -0.04),
                 "soxx-spy<=-3pp & spy>0": (mh["soxx"] - mh["spy"] <= -0.03) & (mh["spy"] > 0)}.items():
    x = mh[cond]
    div[nm] = dict(soxx_next=stat(x["soxx_next"]), spy_next=stat(x["spy_next"]), dates=[str(i.date()) for i in x.index[-12:]])
    print(nm, "N", len(x), "| SOXX next:", {k: div[nm]["soxx_next"].get(k) for k in ("N", "up", "mean", "med", "min", "max")}, "| last:", div[nm]["dates"][-6:])
out["divergence"] = div
out["div_1104"] = dict(soxx=round(float(m.loc[D4, "soxx"]) * 100, 2), spy=round(float(m.loc[D4, "spy"]) * 100, 2),
                       soxx_next=round(float(m.loc[D5, "soxx"]) * 100, 2), spy_next=round(float(m.loc[D5, "spy"]) * 100, 2))
print("div_1104", out["div_1104"])
x = m[(m["soxx"] - m["spy"] <= -0.03) & (m["spy"] > 0)].loc[:"2026-11-04"]
print(x[["soxx", "spy", "soxx_next", "spy_next"]].round(4).tail(25).to_string())

json.dump(out, open("review_stats.json", "w"), ensure_ascii=False, indent=1, default=str)
