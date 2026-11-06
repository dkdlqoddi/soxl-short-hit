"""복기용 추가 통계: 첫 1시간 종가 위치(반등 반납), 프리마켓 연속성, 한국 반도체 급락일과 SOXL 다음 시가,
재검토선별 청산 가격. 출력: review_stats_extra.json"""
import json
import pandas as pd, numpy as np

pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
NY = "America/New_York"
out = {}

def rd(fn, tz=NY):
    df = pd.read_csv(fn, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(tz)
    return df

def stat(x):
    x = pd.Series(x).dropna()
    if not len(x):
        return dict(N=0)
    return dict(N=int(len(x)), up=round(float((x > 0).mean() * 100), 1), mean=round(float(x.mean() * 100), 2), med=round(float(x.median() * 100), 2),
                q25=round(float(x.quantile(.25) * 100), 1), q75=round(float(x.quantile(.75) * 100), 1),
                le10=round(float((x <= -0.10).mean() * 100), 1), le15=round(float((x <= -0.15).mean() * 100), 1),
                min=round(float(x.min() * 100), 1), max=round(float(x.max() * 100), 1))

d = rd("SOXL_1d.csv"); d.index = d.index.normalize().tz_localize(None)
d["pc"] = d["Close"].shift(1); d["gap"] = d["Open"] / d["pc"] - 1
d["oc"] = d["Close"] / d["Open"] - 1; d["oo"] = d["Open"].shift(-1) / d["Open"] - 1
d["ret"] = d["Close"] / d["pc"] - 1; d["prev_ret"] = d["ret"].shift(1)

h = rd("SOXL_1h.csv")
day = h.index.normalize().tz_localize(None)
hm = h.index.hour * 100 + h.index.minute
f = h[hm == 930].copy(); f.index = f.index.normalize().tz_localize(None)
p4 = h[hm == 400].copy(); p4.index = p4.index.normalize().tz_localize(None)
p9 = h[hm == 900].copy(); p9.index = p9.index.normalize().tz_localize(None)
# 애프터마켓 마지막 봉(18:00 또는 19:00 시작)의 종가 = 그날 시간외 마지막 가격
ah = h[(hm >= 1600)].copy(); ah["day"] = ah.index.normalize().tz_localize(None)
ah_last = ah.groupby("day")["Close"].last()
t = pd.DataFrame({"o": f["Open"], "c1": f["Close"], "h1": f["High"], "l1": f["Low"], "pm_first": p4["Open"], "pm_last": p9["Close"]})
t = t.join(d[["pc", "Open", "Close", "gap", "oo", "oc", "prev_ret"]], how="inner")
t["ah_prev"] = ah_last.reindex(t.index).shift(1)                  # 전날 애프터마켓 마지막 가격
t["r1"] = t["c1"] / t["o"] - 1
t["pos1"] = (t["c1"] - t["l1"]) / (t["h1"] - t["l1"])              # 첫 1시간 범위 안 종가 위치
t["give1"] = t["c1"] / t["h1"] - 1                                 # 첫 1시간 고가 대비 종가
t["up1"] = t["h1"] / t["o"] - 1                                    # 첫 1시간 고가 (시가 대비)
t["pm_gap"] = t["pm_first"] / t["pc"] - 1                          # 04:00 첫 체결 vs 전일 종가
t["pm_run"] = t["o"] / t["pm_first"] - 1                           # 04:00 첫 체결 → 정규장 시가
t["ah_to_pm"] = t["pm_first"] / t["ah_prev"] - 1                   # 전날 애프터 마지막 → 04:00 첫 체결
D4 = pd.Timestamp("2026-11-04"); D5 = pd.Timestamp("2026-11-05")
for k in ("r1", "pos1", "give1", "up1"):
    out[f"1104_{k}"] = round(float(t.loc[D4, k]), 4)
for k in ("pm_gap", "pm_run", "ah_to_pm", "gap"):
    out[f"1105_{k}"] = round(float(t.loc[D5, k]), 4)
print({k: v for k, v in out.items()})

th = t.loc[:"2026-11-03"]; gd = th[th["gap"] <= -0.03]
b = {}
b["gap<=-3 & pos1<0.4"] = stat(gd.loc[gd["pos1"] < 0.4, "oo"])
b["gap<=-3 & pos1>=0.6"] = stat(gd.loc[gd["pos1"] >= 0.6, "oo"])
b["gap<=-3 & 0.4<=pos1<0.6"] = stat(gd.loc[(gd["pos1"] >= 0.4) & (gd["pos1"] < 0.6), "oo"])
b["gap<=-3 & up1>=+3 & give1<=-3 (반등 반납)"] = stat(gd.loc[(gd["up1"] >= 0.03) & (gd["give1"] <= -0.03), "oo"])
b["gap<=-3 & up1>=+3 & give1>-3 (반등 유지)"] = stat(gd.loc[(gd["up1"] >= 0.03) & (gd["give1"] > -0.03), "oo"])
b["all & up1>=+4 & give1<=-4"] = stat(th.loc[(th["up1"] >= 0.04) & (th["give1"] <= -0.04), "oo"])
b["all & up1>=+4 & give1>-4"] = stat(th.loc[(th["up1"] >= 0.04) & (th["give1"] > -0.04), "oo"])
b["gap<=-3 & |r1|<1 & pos1<0.4"] = stat(gd.loc[(gd["r1"].abs() < 0.01) & (gd["pos1"] < 0.4), "oo"])
b["gap<=-3 & |r1|<1 & pos1>=0.4"] = stat(gd.loc[(gd["r1"].abs() < 0.01) & (gd["pos1"] >= 0.4), "oo"])
out["first_hour_shape"] = b
print(pd.DataFrame(b).T.to_string())
x = gd.loc[(gd["up1"] >= 0.03) & (gd["give1"] <= -0.03), ["gap", "r1", "up1", "give1", "pos1", "oc", "oo"]]
print(x.round(4).to_string())

# ── 프리마켓 연속성: 04:00 첫 체결이 전일 종가 대비 크게 낮을 때 정규장 시가까지
pm = t.loc[:"2026-11-04"].dropna(subset=["pm_gap", "pm_run"])
c = {}
for nm, cond in {"pm_gap<=-5": pm["pm_gap"] <= -0.05, "pm_gap<=-3": pm["pm_gap"] <= -0.03, "-3<pm_gap<=-1": (pm["pm_gap"] > -0.03) & (pm["pm_gap"] <= -0.01),
                 "pm_gap>=+3": pm["pm_gap"] >= 0.03, "pm_gap>=+5": pm["pm_gap"] >= 0.05, "all": pm["pm_gap"] > -9}.items():
    x = pm[cond]
    c[nm] = dict(pm_run=stat(x["pm_run"]), oc=stat(x["oc"]), gap_final=round(float(x["gap"].median() * 100), 2))
    print(nm, "N", len(x), "04:00→시가:", {k: c[nm]["pm_run"].get(k) for k in ("up", "mean", "med", "q25", "q75")}, "| 시가→종가:", {k: c[nm]["oc"].get(k) for k in ("up", "mean", "med")})
out["premarket_continuation"] = c
print(pm.loc[pm["pm_gap"] <= -0.05, ["pc", "pm_first", "o", "pm_gap", "pm_run", "gap", "oc"]].round(4).tail(25).to_string())

# ── 한국 반도체(SK하이닉스) 급락일 → 같은 날짜 미국 SOXL 시가
hx = rd("000660_KS_1d.csv", "Asia/Seoul"); hx.index = hx.index.normalize().tz_localize(None)
ks = rd("KS11_1d.csv", "Asia/Seoul"); ks.index = ks.index.normalize().tz_localize(None)
k = pd.DataFrame({"hynix": hx["Close"].pct_change(), "kospi": ks["Close"].pct_change()})
j = d[["gap", "oc", "ret", "prev_ret", "oo"]].join(k, how="inner")
j = j.loc["2010-04-01":"2026-11-05"]
e = {}
for nm, cond in {"hynix<=-5": j["hynix"] <= -0.05, "hynix<=-7": j["hynix"] <= -0.07, "hynix<=-5 & prev SOXL<=-5": (j["hynix"] <= -0.05) & (j["prev_ret"] <= -0.05),
                 "kospi<=-3": j["kospi"] <= -0.03, "kospi<=-4": j["kospi"] <= -0.04, "all": j["hynix"] > -9}.items():
    x = j[cond & (j.index < "2026-11-05")]
    e[nm] = dict(gap=stat(x["gap"]), oc=stat(x["oc"]), ret=stat(x["ret"]))
    print(nm, "N", len(x), "| SOXL 갭:", {q: e[nm]["gap"].get(q) for q in ("up", "mean", "med", "q25", "q75")}, "| 시가→종가:", {q: e[nm]["oc"].get(q) for q in ("up", "mean", "med")},
          "| 당일:", {q: e[nm]["ret"].get(q) for q in ("up", "mean", "med")})
out["korea_semis_to_soxl"] = e
out["korea_1105"] = dict(hynix=round(float(j.loc[D5, "hynix"]) * 100, 2), kospi=round(float(j.loc[D5, "kospi"]) * 100, 2), soxl_gap=round(float(j.loc[D5, "gap"]) * 100, 2),
                         soxl_oc=round(float(j.loc[D5, "oc"]) * 100, 2))
print("korea_1105", out["korea_1105"])
print(j.loc[(j["kospi"] <= -0.04)].round(4).tail(20).to_string())

json.dump(out, open("review_stats_extra.json", "w"), ensure_ascii=False, indent=1, default=str)
