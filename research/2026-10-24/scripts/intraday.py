import sys, site; sys.path.insert(0, site.getusersitepackages())
import pandas as pd, numpy as np
data, out = sys.argv[1], sys.argv[2]
def load(name):
    h = pd.read_csv(f"{data}/{name}.csv", header=[0,1], index_col=0)
    h.columns = [c[0].lower() for c in h.columns]
    h = h.apply(pd.to_numeric, errors="coerce").dropna(subset=["close"])
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York")
    return h
def kst(t):
    hh, mm = map(int, t.split(":")); return f"{(hh+13)%24:02d}:{mm:02d}"
h = load("soxl_1h_60d")
print("hourly bars:", h.index[0], "->", h.index[-1], "n=", len(h))
h["t"] = h.index.strftime("%H:%M")
h["absret"] = (h.close/h.open-1).abs()*100
h["rng"] = (h.high-h.low)/h.open*100
g = h.groupby("t").agg(bars=("close","size"), mean_abs_ret_pct=("absret","mean"), mean_range_pct=("rng","mean"), median_volume=("volume","median"))
g["KST(EDT)"] = [kst(t) for t in g.index]
g["vol_share_%"] = (g.median_volume/g.median_volume.sum()*100).round(1)
print("\n=== SOXL hourly profile, last 60 sessions (ET bar start; KST = ET+13h during EDT) ===")
print(g.round(2).to_string())
# share of daily range formed in first regular hour
reg = h.between_time("09:30","15:59")
rows=[]
for day, grp in reg.groupby(reg.index.date):
    if len(grp) < 5: continue
    full = grp.high.max()-grp.low.min()
    first = grp.iloc[0]
    rows.append(dict(day=day, first_hour_range_share=(first.high-first.low)/full*100 if full>0 else np.nan,
                     first_hour_vol_share=first.volume/grp.volume.sum()*100))
r = pd.DataFrame(rows)
print(f"\nfirst regular hour (09:30-10:30 ET = 22:30-23:30 KST): median share of day's range = {r.first_hour_range_share.median():.0f}%, median share of regular volume = {r.first_hour_vol_share.median():.0f}%  (n={len(r)} days)")
m = load("soxl_5m_5d")
print("\n=== 5-minute bars incl. pre/post, by day (ET) ===")
for day, grp in m.groupby(m.index.date):
    pre = grp.between_time("04:00","09:25"); rg = grp.between_time("09:30","15:55"); post = grp.between_time("16:00","19:55")
    f = lambda s, k: (f"{s[k].iloc[0]:.2f}" if len(s) else "-")
    l = lambda s, k: (f"{s[k].iloc[-1]:.2f}" if len(s) else "-")
    print(f"{day} | pre 04:00 first {f(pre,'open')} low {pre.low.min() if len(pre) else float('nan'):.2f} last {l(pre,'close')} | "
          f"reg open {f(rg,'open')} high {rg.high.max():.2f} low {rg.low.min():.2f} close {l(rg,'close')} | "
          f"post first {f(post,'open')} low {post.low.min() if len(post) else float('nan'):.2f} last {l(post,'close')} vol_post {post.volume.sum() if len(post) else 0:,.0f}")
# Oct 21 after-hours -> Oct 22 premarket path (Korean daytime session sits between 20:00 and 04:00 ET)
try:
    ah = m.loc["2026-10-21"].between_time("16:00","19:55"); pm = m.loc["2026-10-22"].between_time("04:00","09:25")
    print("\nOct 21 after-hours (16:00-20:00 ET = Oct 22 05:00-09:00 KST): first %.2f  low %.2f  last %.2f" % (ah.open.iloc[0], ah.low.min(), ah.close.iloc[-1]))
    print("  -> Korean daytime session window (20:00 ET Oct 21 - 04:00 ET Oct 22 = 09:00-17:00 KST Oct 22) not in Yahoo data")
    print("Oct 22 pre-market (04:00-09:30 ET = 17:00-22:30 KST): first %.2f  high %.2f  low %.2f  last %.2f" % (pm.open.iloc[0], pm.high.max(), pm.low.min(), pm.close.iloc[-1]))
    r22 = m.loc["2026-10-22"].between_time("09:30","15:55")
    print("Oct 22 regular: 09:30 open %.2f, 10:30 %.2f, 12:00 %.2f, 14:00 %.2f, 15:55 close %.2f" % (r22.open.iloc[0], r22.between_time("10:30","10:30").close.iloc[0], r22.between_time("12:00","12:00").close.iloc[0], r22.between_time("14:00","14:00").close.iloc[0], r22.close.iloc[-1]))
except Exception as e:
    print("timeline error", e)
g.to_csv(f"{out}/hourly_profile.csv")
