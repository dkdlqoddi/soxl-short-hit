import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import Backtester, trades_for, net
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fp = os.path.expanduser("~/.local/share/fonts/malgun.ttf")
if os.path.exists(fp): font_manager.fontManager.addfont(fp); plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e4e6ea", "grid.linewidth": 0.8, "axes.edgecolor": "#9aa0a6"})
BLUE, ORANGE, GREEN, YELLOW, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#8a8f98", "#1f2328", "#5f6670"
eq = pd.read_csv(os.path.join(here, "data", "shortlist_equity.csv"), index_col=0, parse_dates=True)
sl = pd.read_csv(os.path.join(here, "data", "shortlist.csv"))

# ---- chart 1: equity curves ----
fig, ax = plt.subplots(figsize=(11, 6.2), dpi=150)
series = [("SOXL 보유", GRAY, "-", "SOXL 그냥 보유"), ("매일 시가→종가", GRAY, "--", "매일 시가 매수·종가 매도"),
          ("A", BLUE, "-", "A 저가 마감 & 변동성 큼 (종가→다음 종가)"), ("B", ORANGE, "-", "B RSI(2)<25 & -8% (종가→다음 종가)"),
          ("E", GREEN, "-", "E 하락추세 & 저가 마감 (종가→다음 종가)"), ("S", YELLOW, "-", "S SOXS: +8% & 변동성 큼 (종가→다음 종가)")]
for key, col, ls, lab in series:
    y = eq[key].clip(lower=0.01); ax.plot(eq.index, y, color=col, lw=2 if col != GRAY else 1.6, ls=ls, label=lab)
ax.set_yscale("log"); ax.set_ylim(0.01, 60)
ax.set_yticks([0.01, 0.1, 0.5, 1, 2, 5, 10, 20, 40]); ax.set_yticklabels(["0.01배", "0.1배", "0.5배", "1배", "2배", "5배", "10배", "20배", "40배"])
ax.set_title("추천 규칙의 10년 자산 곡선 (수수료 왕복 0.5% 차감, 매번 전액 투입, 로그 축)", loc="left", fontsize=13, color=INK, pad=12)
ax.text(0, 1.01, "2016-10-24 ~ 2026-10-30, 시작 자산 1배", transform=ax.transAxes, color=MUTED, fontsize=9.5)
# direct end labels
ends = {k: float(eq[k].clip(lower=0.01).iloc[-1]) for k, *_ in series}
order = sorted(ends.items(), key=lambda kv: kv[1])
ypos = []; ymin, ymax = np.log10(0.01), np.log10(60); gap = 0.055 * (ymax - ymin)
for k, v in order:
    y = np.log10(v)
    if ypos and y - ypos[-1] < gap: y = ypos[-1] + gap
    ypos.append(y)
for (k, v), y in zip(order, ypos):
    col = {s[0]: s[1] for s in series}[k]
    txt = f"{k} {v:.0f}배" if v >= 1 else f"{k} {v:.2f}배"
    ax.annotate(txt, (eq.index[-1], 10 ** y), xytext=(8, 0), textcoords="offset points", va="center", ha="left", fontsize=9.5, color=col if col != GRAY else MUTED)
ax.legend(loc="upper left", fontsize=9, frameon=False); ax.set_xlim(eq.index[0], eq.index[-1] + pd.Timedelta(days=420))
fig.tight_layout(); fig.savefig(os.path.join(here, "charts", "01_equity_curves.png")); plt.close(fig)

# ---- chart 2: IS vs OOS ----
S = pd.read_csv(os.path.join(here, "data", "singles.csv")); P = pd.read_csv(os.path.join(here, "data", "pairs.csv"))
A = pd.concat([S[S.a != "ALL"], P[~P.redundant]]); A = A[A.n >= 50]
top = A.sort_values("is_total", ascending=False).head(200)
fig, ax = plt.subplots(figsize=(9.5, 6.2), dpi=150)
ax.scatter(top.is_total, top.oos_total, s=22, color=GRAY, alpha=0.55, edgecolor="white", linewidth=0.5, label="표본 안 상위 200개 규칙")
ax.axhline(0, color=INK, lw=1); ax.axhline(top.oos_total.median(), color=ORANGE, lw=1.2, ls="--")
ax.annotate(f"표본 밖 중앙값 {top.oos_total.median():.0f}%", (top.is_total.max(), top.oos_total.median()), xytext=(-4, 6), textcoords="offset points", ha="right", color=ORANGE, fontsize=9.5)
marks = {"A": (["CLV<0.2", "ATRhi"], "CC", BLUE), "B": (["RSI2<25", "ret<-8%"], "CC", ORANGE), "E": (["ADX>25dn", "CLV<0.2"], "CC", GREEN), "C": (["down2", "gap<-2%"], "O5C", YELLOW)}
for tag, (keys, tpl, col) in marks.items():
    r = sl[sl.tag == tag].iloc[0]
    ax.scatter([r.is_total], [r.oos_total], s=80, color=col, edgecolor="white", linewidth=1.2, zorder=5)
    ax.annotate(tag, (r.is_total, r.oos_total), xytext=(7, 4), textcoords="offset points", color=col, fontsize=11, fontweight="bold")
ax.set_xlabel("표본 안 수익률 2016-10 ~ 2021-10 (%)"); ax.set_ylabel("표본 밖 수익률 2021-11 ~ 2026-10 (%)")
ax.set_title("표본 안에서 좋았던 규칙은 표본 밖에서 어땠나", loc="left", fontsize=13, color=INK, pad=12)
ax.text(0, 1.01, f"거래 50건 이상인 26,642개 규칙 중 표본 안 상위 200개. 표본 밖 플러스 {(top.oos_total > 0).sum()}개 / 200", transform=ax.transAxes, color=MUTED, fontsize=9.5)
ax.legend(loc="upper right", fontsize=9, frameon=False)
fig.tight_layout(); fig.savefig(os.path.join(here, "charts", "02_is_vs_oos.png")); plt.close(fig)

# ---- chart 3: random reference ----
bt = Backtester(os.path.join(here, "data")); rng = np.random.default_rng(7); n = len(bt.idx)
O, C = bt.px["SOXL"]
ei, ep, xi, xp = trades_for(np.ones(n, dtype=bool), "CC", O, C)
base = np.zeros(n); base[ei] = np.log1p(net(ep, xp))
tot_cc = np.array([np.exp((base * (rng.random(n) < 0.12)).sum()) for _ in range(6000)])
tot_o5 = []
for _ in range(2500):
    s = rng.random(n) < 0.04
    a, b, c, d = trades_for(s, "O5C", O, C); tot_o5.append(np.exp(np.log1p(net(b, d)).sum()))
tot_o5 = np.array(tot_o5)
fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), dpi=150)
for ax, tot, title, marks in [
    (axes[0], tot_cc, "종가→다음 종가, 무작위로 12%의 날 거래 (6,000회)", [("A", 1 + sl[sl.tag == "A"].total.iloc[0] / 100, BLUE), ("B", 1 + sl[sl.tag == "B"].total.iloc[0] / 100, ORANGE), ("G", 1 + sl[sl.tag == "G"].total.iloc[0] / 100, GREEN)]),
    (axes[1], tot_o5, "시가→5일째 종가, 무작위로 4%의 날 진입 (2,500회)", [("C", 1 + sl[sl.tag == "C"].total.iloc[0] / 100, YELLOW)])]:
    bins = np.logspace(-2, 2.2, 60)
    ax.hist(tot, bins=bins, color=GRAY, alpha=0.8, edgecolor="white", linewidth=0.4)
    ax.set_xscale("log"); ax.set_xticks([0.01, 0.1, 1, 10, 100]); ax.set_xticklabels(["0.01배", "0.1배", "1배", "10배", "100배"])
    q = np.percentile(tot, 99.9); ax.axvline(q, color=INK, lw=1, ls=":"); ax.annotate("상위 0.1%", (q, ax.get_ylim()[1] * 0.92), xytext=(4, 0), textcoords="offset points", fontsize=9, color=MUTED)
    for j, (tag, v, col) in enumerate(sorted(marks, key=lambda m: m[1])):
        ax.axvline(v, color=col, lw=2); ax.annotate(f"{tag} {v:.0f}배", (v, ax.get_ylim()[1] * (0.78 - 0.12 * j)), xytext=(4, 0), textcoords="offset points", color=col, fontsize=10, fontweight="bold")
    ax.set_title(title, loc="left", fontsize=11, color=INK); ax.set_xlabel("10년 뒤 자산 배수 (수수료 차감)"); ax.set_ylabel("무작위 신호 집합 수")
fig.suptitle("찾아낸 규칙 vs 무작위 신호가 운으로 내는 범위 (SOXL)", x=0.01, ha="left", fontsize=13, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(here, "charts", "03_random_reference.png")); plt.close(fig)
print("charts done; random cc p99.9 %.1fx best %.1fx | o5c p99.9 %.1fx best %.1fx" % (np.percentile(tot_cc, 99.9), tot_cc.max(), np.percentile(tot_o5, 99.9), tot_o5.max()))
