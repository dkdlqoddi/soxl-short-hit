"""세 노트의 중심 예상가·전체 범위가 과거 24시간 분포에서 차지하는 비율 (Claude Fable Max).
2년 1시간봉 애프터마켓(17시 EST 봉 종가) → 다음 거래일 같은 봉, 2026-11-03까지(이번 회차 제외).
실행: python3 stats_range.py → stats_range.json
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D = Path(__file__).resolve().parent
H = D / "hist"
kd = pd.read_pickle(H / "d_KORU.pkl"); kd.index = pd.to_datetime(kd.index.strftime("%Y-%m-%d"))
if pd.isna(kd.loc["2026-11-05", "Close"]):
    kd.loc["2026-11-05", "Close"] = 6.53
kh = pd.read_pickle(H / "h_KORU.pkl"); kh.index = kh.index.tz_convert("America/New_York")
ah = kh[kh.index.hour == 17]["Close"]; ah.index = pd.to_datetime(ah.index.strftime("%Y-%m-%d")); ah = ah[~ah.index.duplicated(keep="last")]
pc = kd["Close"].shift(1)
tr = pd.concat([kd["High"] - kd["Low"], (kd["High"] - pc).abs(), (kd["Low"] - pc).abs()], axis=1).max(axis=1)
kd["atrp"] = tr.rolling(14).mean() / kd["Close"]
a = pd.DataFrame({"ah": ah}).join(kd[["Close", "atrp"]], how="inner")
a["prem"] = a["ah"] / a["Close"] - 1
nxt = pd.Series(kd.index, index=kd.index).shift(-1)
ok = (a.index.to_series().shift(-1) == nxt.reindex(a.index)) & (a["prem"].abs() <= 0.15) & (a["prem"].shift(-1).abs() <= 0.15)
a["ret24"] = (a["ah"].shift(-1) / a["ah"] - 1).where(ok)
a0 = a.dropna(subset=["ret24", "atrp"]).loc[:"2026-11-03"]
hv = a0[a0["atrp"] >= 0.12]
bands = {"Claude 중심 −5~+1%": (-0.05, 0.01), "Argon 중심 −4.1~+0.2%": (-0.041, 0.002), "Codex 중심 −2.8~−0.5%": (-0.0283, -0.0047),
         "Claude 전체 −17.1~+8.3%": (-0.171, 0.083), "Argon 범위 −14.0~+12.5%": (-0.140, 0.125), "Codex 대표 −13.2~+11.3%": (-0.132, 0.113),
         "±1.5 ATR(13.85%) = ±20.8%": (-0.208, 0.208), "5~95% 분위(고변동) −19.6~+20.1%": (-0.196, 0.201)}
out = {"n_all": int(len(a0)), "n_hv": int(len(hv)), "hv_period": f"{hv.index[0].date()}~{hv.index[-1].date()}", "bands": {}}
for nm, (lo, hi) in bands.items():
    f = lambda s: [round(float(((s >= lo) & (s <= hi)).mean() * 100), 1), round(float((s < lo).mean() * 100), 1), round(float((s > hi).mean() * 100), 1)]
    out["bands"][nm] = {"전체[안,아래,위]%": f(a0["ret24"]), "ATR≥12%[안,아래,위]%": f(hv["ret24"])}
    print(nm, out["bands"][nm])
out["hv_tail"] = {"<=-30%": int((hv["ret24"] <= -0.30).sum()), "<=-20%": int((hv["ret24"] <= -0.20).sum()), ">=+20%": int((hv["ret24"] >= 0.20).sum()), "min": round(float(hv["ret24"].min() * 100), 1), "max": round(float(hv["ret24"].max() * 100), 1),
                  "sd": round(float(hv["ret24"].std() * 100), 1), "down_given": {str(q): round(float(hv["ret24"].quantile(q) * 100), 1) for q in (0.01, 0.025, 0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95, 0.975, 0.99)}}
print(out["hv_tail"])
json.dump(out, open(D / "stats_range.json", "w"), ensure_ascii=False, indent=1)
