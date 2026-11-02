"""Render markdown tables for the research note from the analysis / confirmation CSVs.

Usage: python3 tables.py <analysis_dir> <confirm_dir>
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os
import pandas as pd
import numpy as np

BUY_KO = ["RSI14<30", "RSI2<10", "스토K<20", "종가<BB하단", "CCI<-100", "EMA9/21 골든", "MACD 골든",
          "Supertrend 상승", "PSAR 상승", "+DI>-DI&ADX>20", "20봉 신고가", "시가범위 돌파", "전일고가 돌파",
          "VWAP 상향돌파", "종가>VWAP", "거래량2배&양봉", "저가근처 마감", "첫 1시간", "종가>SMA200(일)", "한봉 -2%"]
SELL_KO = ["RSI14>70", "RSI2>90", "스토K>80", "종가>BB상단", "CCI>100", "EMA9/21 데드", "MACD 데드",
           "Supertrend 하락전환", "PSAR 하락전환", "-DI 교차", "10봉 신저가", "VWAP 하향돌파", "EMA9 하향돌파", "한봉 +2%",
           "익절+3%", "손절-2%", "트레일링2%", "샹들리에2ATR", "4시간", "장마감"]
TF_KO = {"5": "5분봉(1년)", "15": "15분봉", "30": "30분봉", "60": "1시간봉", "120": "2시간봉"}


def ko(name, tbl_en, tbl_ko, joiner):
    parts = name.split(joiner)
    out = []
    for p in parts:
        p = p.strip()
        out.append(tbl_ko[tbl_en.index(p)] if p in tbl_en else p)
    return joiner.join(out)


BUY_EN = ["RSI14<30", "RSI2<10", "StochK<20", "Close<BB_lower", "CCI<-100", "EMA9xEMA21_up", "MACD_cross_up",
          "Supertrend_bull", "PSAR_bull", "DMI_bull&ADX>20", "Donchian20_break", "ORB30_break", "PrevDayHigh_break",
          "Close_x_VWAP_up", "Close>VWAP", "VolSpike&UpBar", "CLV<0.2", "FirstHour", "Close>SMA200d", "BarDrop<=-2%"]
SELL_EN = ["RSI14>70", "RSI2>90", "StochK>80", "Close>BB_upper", "CCI>100", "EMA9xEMA21_down", "MACD_cross_down",
           "Supertrend_flip_bear", "PSAR_flip_bear", "DMI_cross_bear", "Donchian10_low_break", "Close_x_VWAP_down",
           "Close_x_EMA9_down", "BarSurge>=+2%", "TP+3%", "SL-2%", "Trail2%", "Chandelier2ATR", "Time4h", "EOD"]


def kob(s):
    return ko(s, BUY_EN, BUY_KO, " & ")


def kos(s):
    return ko(s, SELL_EN, SELL_KO, " | ")


def md(df, cols, headers, fmt):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in df.itertuples(index=False):
        d = r._asdict()
        cells = []
        for c, f in zip(cols, fmt):
            v = d[c]
            cells.append(f(v) if callable(f) else (f % v if isinstance(v, (int, float, np.floating, np.integer)) and not pd.isna(v) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    adir, cdir = sys.argv[1], sys.argv[2]
    tfs = [tf for tf in ["15", "30", "60", "120", "5"] if os.path.exists(os.path.join(adir, f"screen_{tf}.csv"))]
    print("# 3. 1단계 요약 (시간봉별)\n")
    rows = []
    for tf in tfs:
        df = pd.read_csv(os.path.join(adir, f"screen_{tf}.csv"))
        ok = df[df.trades >= 30]
        best = ok.sort_values("net_mult", ascending=False).iloc[0]
        rows.append(dict(tf=TF_KO[tf], n=len(df), nok=len(ok), pos=(ok.net_pct > 0).mean() * 100, med=ok.net_pct.median(), q90=ok.net_pct.quantile(0.9), q99=ok.net_pct.quantile(0.99), best=best.net_pct, bestname=kob(best.buy) + " → " + kos(best.sell), bothpos=((ok.y1_pct > 0) & (ok.y2_pct > 0)).mean() * 100))
    print(md(pd.DataFrame(rows), ["tf", "nok", "pos", "med", "q90", "q99", "best", "bestname", "bothpos"], ["시간봉", "조합 수(거래≥30)", "플러스 비율 %", "중앙값 %", "상위 10% %", "상위 1% %", "최고 %", "최고 조합", "두 해 모두 플러스 %"], ["%s", "%d", "%.1f", "%.0f", "%.0f", "%.0f", "%.0f", "%s", "%.1f"]))
    for tf in tfs:
        df = pd.read_csv(os.path.join(adir, f"screen_{tf}.csv"))
        ok = df[df.trades >= 30]
        top = ok.sort_values("net_mult", ascending=False).head(10).copy()
        top["buy_ko"] = top.buy.map(kob)
        top["sell_ko"] = top.sell.map(kos)
        print(f"\n## {TF_KO[tf]} 상위 10 (1단계, 거래 30회 이상)\n")
        print(md(top, ["buy_ko", "sell_ko", "trades", "win_pct", "net_pct", "mdd_pct", "pf", "avg_ret_pct", "avg_bars", "y1_pct", "y2_pct"],
                 ["매수", "매도", "거래", "승률 %", "2년 순수익 %", "최대낙폭 %", "손익비", "평균/회 %", "평균 보유(봉)", "1년차 %", "2년차 %"],
                 ["%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.2f", "%.2f", "%.1f", "%.0f", "%.0f"]))
        rb = pd.read_csv(os.path.join(adir, f"robust_buy_{tf}.csv")).head(8).copy()
        rb["buy_ko"] = rb.buy.map(kob)
        print(f"\n### {TF_KO[tf]} 매수 규칙 강건성 (매도 210가지 전체에 대한 분포)\n")
        print(md(rb, ["buy_ko", "pct_pos", "median_net", "q75_net", "best_net", "median_mdd", "median_trades"], ["매수 규칙", "플러스 비율 %", "중앙값 %", "상위 25% %", "최고 %", "낙폭 중앙값 %", "거래 중앙값"], ["%s", "%.0f", "%.0f", "%.0f", "%.0f", "%.0f", "%.0f"]))
        rs = pd.read_csv(os.path.join(adir, f"robust_sell_{tf}.csv")).head(8).copy()
        rs["sell_ko"] = rs.sell.map(kos)
        print(f"\n### {TF_KO[tf]} 매도 규칙 강건성 (매수 210가지 전체에 대한 분포)\n")
        print(md(rs, ["sell_ko", "pct_pos", "median_net", "q75_net", "best_net", "median_mdd", "median_trades"], ["매도 규칙", "플러스 비율 %", "중앙값 %", "상위 25% %", "최고 %", "낙폭 중앙값 %", "거래 중앙값"], ["%s", "%.0f", "%.0f", "%.0f", "%.0f", "%.0f", "%.0f"]))
        s = pd.read_csv(os.path.join(adir, f"singles_{tf}.csv"))
        s["name_ko"] = [kob(n) if side == "buy" else kos(n) for side, n in zip(s.side, s.name)]
        print(f"\n### {TF_KO[tf]} 조건별 한계 효과 (그 조건을 포함한 모든 조합의 분포)\n")
        print(md(s.sort_values(["side", "median_net_pct"], ascending=[True, False]), ["side", "name_ko", "n_combos", "median_net_pct", "pct_positive", "best_net_pct", "median_trades"], ["쪽", "조건", "조합 수", "중앙값 %", "플러스 비율 %", "최고 %", "거래 중앙값"], ["%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.0f"]))
    sfp = os.path.join(cdir, "confirm_summary.csv")
    if os.path.exists(sfp):
        S = pd.read_csv(sfp)
        S["buy_ko"] = S.buy.map(kob)
        S["sell_ko"] = S.sell.map(kos)
        print("\n# 2단계: Strategy Tester 확인\n")
        for tf in tfs:
            st = S[S.tf.astype(str) == tf].sort_values("net_pct", ascending=False)
            if st.empty:
                continue
            print(f"\n## {TF_KO[tf]}\n")
            print(md(st, ["label", "buy_ko", "sell_ko", "trades", "win_pct", "net_pct", "mdd_pct", "pf", "params"], ["구분", "매수", "매도", "거래", "승률 %", "순수익 %", "최대낙폭 %", "손익비", "파라미터"], ["%s", "%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.2f", "%s"]))


if __name__ == "__main__":
    main()
