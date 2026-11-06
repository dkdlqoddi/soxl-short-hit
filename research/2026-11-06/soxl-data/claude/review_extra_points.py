"""노트 본문에 쓰는 보조 수치: SOXX 시간외 −1% 도달 시각, 11/5 장중 변곡 시각, 구간 기여(프리마켓 시작을 18:10 KST로)."""
import json
import numpy as np, pandas as pd
from load import load

T = lambda x: pd.Timestamp(x, tz="America/New_York")
kst = lambda ts: ts.tz_convert("Asia/Seoul").strftime("%m/%d %H:%M")
s, sx = load("SOXL"), load("SOXX")
out = {}
SOXX_C4 = 450.41 / 3
a = sx[(sx.index >= T("2026-11-04 16:00")) & (sx.index <= T("2026-11-04 19:59"))]
hit = a[a["Close"] <= SOXX_C4 * 0.99]
t0 = hit.index[0]
out["soxx_ah_minus1"] = dict(kst=kst(t0), et=str(t0), soxx=round(float(hit["Close"].iloc[0]), 3), soxl=round(float(s[s.index <= t0]["Close"].iloc[-1]), 2),
                             soxx_last=round(float(a["Close"].iloc[-1]), 3), soxx_last_pct=round((float(a["Close"].iloc[-1]) / SOXX_C4 - 1) * 100, 2))
def seg(a_, b_):
    return s[(s.index >= T(a_)) & (s.index <= T(b_))]
pts = {}
for nm, (a_, b_) in {"1105_0930_1029": ("2026-11-05 09:30", "2026-11-05 10:29"), "1105_1030_1129": ("2026-11-05 10:30", "2026-11-05 11:29"),
                     "1105_1130_1559": ("2026-11-05 11:30", "2026-11-05 15:59"), "1105_1500_1559": ("2026-11-05 15:00", "2026-11-05 15:59")}.items():
    x = seg(a_, b_)
    pts[nm] = dict(first=round(float(x["Open"].iloc[0]), 2), last=round(float(x["Close"].iloc[-1]), 2), high=round(float(x["High"].max()), 2), high_kst=kst(x["High"].idxmax()),
                   low=round(float(x["Low"].min()), 2), low_kst=kst(x["Low"].idxmin()))
out["points_1105"] = pts
chain = [("11/4 23:30 시가(기준가)", 70.03), ("11/5 00:29 첫 1시간 종가", 70.06), ("11/5 06:00 정규장 종가", 66.68), ("11/5 09:59 애프터마켓 마지막", 64.01),
         ("11/5 18:10 프리마켓", float(s.loc[T("2026-11-05 04:10"), "Close"])), ("11/5 23:14 프리마켓 마지막 체결", 57.82), ("11/5 23:30 시가(만기)", 56.95)]
tot = np.log(56.95 / 70.03); rows = []
for (n0, p0), (n1, p1) in zip(chain[:-1], chain[1:]):
    rows.append(dict(frm=n0, to=n1, p0=round(p0, 2), p1=round(p1, 2), chg=round((p1 / p0 - 1) * 100, 2), share=round(np.log(p1 / p0) / tot * 100, 1)))
out["contrib_1810"] = rows
out["chunks"] = dict(regular_1104=round((66.68 / 70.03 - 1) * 100, 2), after=round((64.01 / 66.68 - 1) * 100, 2), asia_pm_open=round((56.95 / 64.01 - 1) * 100, 2),
                     share_regular=round(np.log(66.68 / 70.03) / tot * 100, 1), share_after=round(np.log(64.01 / 66.68) / tot * 100, 1), share_rest=round(np.log(56.95 / 64.01) / tot * 100, 1))
# 재검토선 시점 가격 대비 만기가
out["exit_vs_expiry"] = {k: round((56.95 / v - 1) * 100, 1) for k, v in {"argon_0023_69.89": 69.89, "break_0044_67.18": 67.18, "codex_0100_64.58": 64.575, "close_0600_66.68": 66.68, "ah_0959_64.01": 64.01, "pm_1810_60.24": 60.24}.items()}
out["exit_vs_base"] = {k: round((v / 70.03 - 1) * 100, 1) for k, v in {"argon_0023_69.89": 69.89, "break_0044_67.18": 67.18, "codex_0100_64.58": 64.575, "close_0600_66.68": 66.68, "ah_0959_64.01": 64.01, "pm_1810_60.24": 60.24}.items()}
# Claude 지정가 제안의 결과
out["limit_orders"] = {str(l): dict(to_close_1104=round((66.68 / l - 1) * 100, 1), to_expiry=round((56.95 / l - 1) * 100, 1), to_close_1105=round((40.87 / l - 1) * 100, 1)) for l in (67.2, 64.0)}
# 11/5 종가 지표
out["clv_1104"] = round((66.68 - 62.23) / (75.29 - 62.23), 3); out["clv_1105"] = round((40.87 - 40.59) / (57.84 - 40.59), 3)
x = seg("2026-11-05 16:00", "2026-11-05 19:59")
out["ah_1105"] = dict(last=round(float(x["Close"].iloc[-1]), 2), last_kst=kst(x.index[-1]), low=round(float(x["Low"].min()), 2), low_kst=kst(x["Low"].idxmin()), high=round(float(x["High"].max()), 2), high_kst=kst(x["High"].idxmax()))
json.dump(out, open("review_extra_points.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
