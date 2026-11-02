"""Charts for the 2026-11-02 SOXL day-trade combination study.

Usage: python3 charts.py <analysis_dir> <confirm_dir> <charts_dir>
  analysis_dir: screen_<tf>.csv (+ random_<tf>.csv if present)
  confirm_dir : confirm_summary.csv, confirm_equity.csv, confirm_trades.csv
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

FONT = os.path.expanduser("~/.local/share/fonts/malgun.ttf")
if os.path.exists(FONT):
    fm.fontManager.addfont(FONT)
    plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False

BUY_KO = ["RSI14<30", "RSI2<10", "스토캐스틱K<20", "종가<BB하단", "CCI<-100", "EMA9/21 골든", "MACD 골든",
          "Supertrend 상승", "PSAR 상승", "+DI>-DI&ADX>20", "20봉 신고가", "시가범위(30분) 돌파", "전일 고가 돌파",
          "VWAP 상향돌파", "종가>VWAP", "거래량2배&양봉", "저가근처 마감", "첫 1시간", "종가>일봉SMA200", "한봉 -2%"]
SELL_KO = ["RSI14>70", "RSI2>90", "스토캐스틱K>80", "종가>BB상단", "CCI>100", "EMA9/21 데드", "MACD 데드",
           "Supertrend 하락전환", "PSAR 하락전환", "-DI 상향교차", "10봉 신저가", "VWAP 하향돌파", "EMA9 하향돌파", "한봉 +2%",
           "익절 +3%", "손절 -2%", "트레일링 2%", "샹들리에 2ATR", "4시간 경과", "장 마감"]
TF_KO = {"5": "5분봉(1년)", "15": "15분봉", "30": "30분봉", "60": "1시간봉", "120": "2시간봉"}


def heatmap(adir, cdir_out, tf):
    fp = os.path.join(adir, f"screen_{tf}.csv")
    if not os.path.exists(fp):
        return
    df = pd.read_csv(fp)
    s = df[(df.n_buy == 1) & (df.n_sell == 1)]
    M = np.full((20, 20), np.nan)
    for r in s.itertuples():
        M[int(r.buy_a), int(r.sell_a)] = r.net_pct if r.trades >= 10 else np.nan
    fig, ax = plt.subplots(figsize=(13, 10))
    v = np.nanmax(np.abs(M)) if np.isfinite(np.nanmax(np.abs(M))) else 100
    v = min(v, 200)
    im = ax.imshow(M, cmap="RdYlGn", vmin=-v, vmax=v, aspect="auto")
    ax.set_xticks(range(20)); ax.set_xticklabels(SELL_KO, rotation=60, ha="right", fontsize=9)
    ax.set_yticks(range(20)); ax.set_yticklabels(BUY_KO, fontsize=9)
    ax.set_xlabel("매도 조건 (1개)"); ax.set_ylabel("매수 조건 (1개)")
    period = "1년" if tf == "5" else "2년"
    ax.set_title(f"SOXL {TF_KO[tf]}: 매수 조건 1개 × 매도 조건 1개의 {period} 순수익률 (%) — 수수료 0.5% 왕복, 최대 24시간 보유")
    for i in range(20):
        for j in range(20):
            if np.isfinite(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(im, ax=ax, label="순수익률 %")
    fig.tight_layout()
    fig.savefig(os.path.join(cdir_out, f"heatmap_1x1_{tf}.png"), dpi=130)
    plt.close(fig)


def distribution(adir, cdir_out, tfs):
    fig, axes = plt.subplots(1, len(tfs), figsize=(4.2 * len(tfs), 4), sharey=False)
    if len(tfs) == 1:
        axes = [axes]
    for ax, tf in zip(axes, tfs):
        fp = os.path.join(adir, f"screen_{tf}.csv")
        if not os.path.exists(fp):
            continue
        df = pd.read_csv(fp)
        ok = df[df.trades >= 30]
        bins = np.linspace(-100, 300, 81)
        ax.hist(ok.net_pct.clip(-100, 300), bins=bins, color="#4C72B0", alpha=0.8, label=f"실제 지표 조합 ({len(ok):,})")
        rf = os.path.join(adir, f"random_{tf}.csv")
        if os.path.exists(rf):
            rd = pd.read_csv(rf)
            rok = rd[rd.trades >= 30]
            ax.hist(rok.net_pct.clip(-100, 300), bins=bins, histtype="step", color="#C44E52", lw=1.5, label=f"무작위 매수 × 같은 매도 ({len(rok):,})")
        ax.axvline(0, color="k", lw=0.8)
        ax.set_title(f"{TF_KO[tf]}: 2년 순수익률 분포")
        ax.set_xlabel("순수익률 % (거래 30회 이상)")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(cdir_out, "distribution_all_tf.png"), dpi=130)
    plt.close(fig)


from tables import kob as KOB, kos as KOS


def equity_curves(cdir, cdir_out, tfs):
    sfp, efp = os.path.join(cdir, "confirm_summary.csv"), os.path.join(cdir, "confirm_equity.csv")
    if not (os.path.exists(sfp) and os.path.exists(efp)):
        return
    S = pd.read_csv(sfp)
    E = pd.read_csv(efp)
    E["date"] = pd.to_datetime(E["date"])
    fig, axes = plt.subplots(len(tfs), 1, figsize=(12, 4 * len(tfs)))
    if len(tfs) == 1:
        axes = [axes]
    for ax, tf in zip(axes, tfs):
        st = S[(S.tf.astype(str) == tf) & (S.id < 1000) & (~S.label.str.contains("var"))].sort_values("tv_net_pct", ascending=False)
        st = st.drop_duplicates(subset=["buy"]).head(5)   # five best distinct buy rules (official Strategy Tester net)
        first = True
        for r in st.itertuples():
            e = E[E.id == r.id].sort_values("date")
            if e.empty:
                continue
            if first:
                bh = e.close / e.close.iloc[0] * 100
                ax.plot(e.date, bh, color="gray", lw=1.2, ls="--", label="SOXL 단순 보유")
                first = False
            ax.plot(e.date, e.equity / 8200 * 100, lw=1.3, label=f"{KOB(r.buy)} → {KOS(r.sell)} ({r.tv_net_pct:+.0f}%, 낙폭 {r.tv_mdd_pct:.0f}%, {int(r.tv_trades)}회)")
        ax.set_yscale("log")
        ax.set_ylabel("자산 (시작=100, 로그)")
        ax.set_title(f"{TF_KO[tf]}: Strategy Tester 기준 매수 규칙별 최고 전략 5개의 자산 곡선 (초기 $8,200, 수수료 0.25%/편도, 24시간 안 청산)")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(cdir_out, "equity_top5_by_tf.png"), dpi=130)
    plt.close(fig)


def is_oos(adir, cdir_out, tfs):
    fig, axes = plt.subplots(1, len(tfs), figsize=(4.2 * len(tfs), 4))
    if len(tfs) == 1:
        axes = [axes]
    for ax, tf in zip(axes, tfs):
        fp = os.path.join(adir, f"screen_{tf}.csv")
        if not os.path.exists(fp):
            continue
        df = pd.read_csv(fp)
        ok = df[df.trades >= 30]
        top = ok.sort_values("y1_pct", ascending=False).head(200)
        ax.scatter(ok.y1_pct.clip(-100, 400), ok.y2_pct.clip(-100, 400), s=3, alpha=0.15, color="gray", label="전체")
        ax.scatter(top.y1_pct.clip(-100, 400), top.y2_pct.clip(-100, 400), s=8, color="#C44E52", label="1년차 상위 200")
        ax.axhline(0, color="k", lw=0.6); ax.axvline(0, color="k", lw=0.6)
        pos = (top.y2_pct > 0).mean() * 100
        ax.set_title(f"{TF_KO[tf]}: 1년차 vs 2년차\n1년차 상위 200개 중 2년차 플러스 {pos:.0f}%")
        ax.set_xlabel("1년차 수익률 % (2024-11~2025-10)"); ax.set_ylabel("2년차 수익률 % (2025-11~2026-10)")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(cdir_out, "is_oos_all_tf.png"), dpi=130)
    plt.close(fig)


def main():
    adir, cdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    tfs = [tf for tf in ["15", "30", "60", "120", "5"] if os.path.exists(os.path.join(adir, f"screen_{tf}.csv"))]
    for tf in tfs:
        heatmap(adir, out, tf)
    distribution(adir, out, tfs)
    is_oos(adir, out, [tf for tf in tfs if tf != "5"])
    equity_curves(cdir, out, tfs + (["5"] if os.path.exists(os.path.join(adir, "screen_5.csv")) else []))
    print("charts written to", out)


if __name__ == "__main__":
    main()
