"""Assemble the stage-2 (Strategy Tester confirmation) sections of the research note.

Usage: python3 build_note_stage2.py <analysis_dir> <jobs.json> <jobs_extra.json> <out.md>
"""
import sys, site
sys.path.insert(0, site.getusersitepackages())
import os, json
import pandas as pd
import numpy as np
from tables import kob, kos, TF_KO, md

LABEL_KO = {"top": "상위", "robustbuy": "강건 매수", "robustsell": "강건 매도", "calmar": "칼마(위험 대비)", "best": "범주 최고", "baseline": "기준선"}


def label_ko(l):
    if l.startswith("baseline_firsthour_EOD"):
        return "기준선: 첫 봉 매수→장 마감"
    if l.startswith("baseline_firsthour_4h"):
        return "기준선: 첫 봉 매수→4시간"
    if l.startswith("baseline_CLV_TP3"):
        return "기준선: 저가근처 마감→익절3%"
    if l.startswith("baseline_drop2_EOD"):
        return "기준선: 한봉 −2%→장 마감"
    if "_var_" in l:
        base, var = l.split("_var_")
        return f"{label_ko(base)} 변형({var})"
    for k, v in LABEL_KO.items():
        if l.startswith(k):
            rest = l[len(k):]
            if k == "best":
                return "범주 최고 " + rest.replace("_", " ").replace("buy", "매수").replace("sell", "매도").strip()
            return v + " " + rest
    return l


def main():
    adir, jobs_fp, extra_fp, out = sys.argv[1:5]
    S = pd.read_csv(os.path.join(adir, "confirm_summary.csv"))
    jobs = {j["id"]: j for j in json.load(open(jobs_fp))}
    if os.path.exists(extra_fp):
        for j in json.load(open(extra_fp)):
            jobs[j["id"]] = j
    S["screen_net"] = S.id.map(lambda i: jobs.get(i, {}).get("screen_net_pct", np.nan))
    S["screen_trades"] = S.id.map(lambda i: jobs.get(i, {}).get("screen_trades", np.nan))
    S["buy_ko"] = S.buy.map(kob)
    S["sell_ko"] = S.sell.map(kos)
    S["label_ko"] = S.label.map(label_ko)
    S["gap"] = S.tv_net_pct - S.screen_net
    main_ = S[S.id < 1000]
    extra = S[S.id >= 1000]
    L = []
    L.append("## 6. 2단계: TradingView Strategy Tester 확인\n")
    L.append("1단계 상위 조합·강건한 매수/매도 규칙의 최고 짝·위험 대비 최고·범주별 최고·기준선·파라미터 변형을 `strategy.pine`으로 TradingView 공식 엔진에서 다시 돌렸다(초기 자본 $8,200, 정수 주 수, 수수료 0.25%/편도, 봉 안 체결 모델 \"4 ticks per bar\"). 표의 **순수익·낙폭·거래·손익비는 Strategy Tester 'Key stats' 값**이고, \"1단계\"는 같은 조합의 스크리너 값이다. 낙폭은 봉 안 저가 기준이라 1단계보다 크게 나온다.\n")
    # overall agreement
    m = main_[~main_.label.str.contains("var")].dropna(subset=["tv_net_pct", "screen_net"])
    if len(m):
        corr = np.corrcoef(m.tv_net_pct, m.screen_net)[0, 1]
        L.append(f"- 확인한 조합 {len(m)}개(변형 제외)에서 1단계 수익률과 Strategy Tester 수익률의 상관은 {corr:.2f}, 차이(테스터 − 1단계)의 중앙값은 {m.gap.median():+.0f}%p, 1단계가 +100% 이상이던 조합 중 테스터에서도 +100% 이상인 것은 {((m.screen_net >= 100) & (m.tv_net_pct >= 100)).sum()}/{(m.screen_net >= 100).sum()}개다.")
        big = m[m.gap.abs() >= 40]
        L.append(f"- 차이가 40%p 이상인 조합은 {len(big)}개이며, 거의 전부 **종가 체결형 매도(PSAR·−DI·VWAP 전환, RSI2>90 등)에서 \"청산 봉에 새 매수 신호가 나면 같은 종가에 다시 사는\" 1단계 규칙을 테스터가 허용하지 않아** 생긴 차이다(7절에서 \"보유 연장\" 규칙으로 맞추면 사라짐). 봉 안 체결형 매도(샹들리에·익절·손절)나 거래가 적은 조합은 두 단계가 거의 같다.\n")
    for tf in ["15", "30", "60", "120", "5"]:
        st = main_[(main_.tf.astype(str) == tf)].copy()
        if st.empty:
            continue
        st = st[~st.label.str.contains("var")].sort_values("tv_net_pct", ascending=False)
        L.append(f"### 6.{['15', '30', '60', '120', '5'].index(tf) + 1} {TF_KO[tf]}\n")
        L.append(md(st, ["label_ko", "buy_ko", "sell_ko", "tv_trades", "tv_win_pct", "tv_net_pct", "tv_mdd_pct", "tv_pf", "screen_net", "screen_trades"],
                    ["구분", "매수", "매도", "거래", "승률 %", "순수익 %", "최대낙폭 %", "손익비", "1단계 순수익 %", "1단계 거래"],
                    ["%s", "%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.2f", "%.0f", "%.0f"]) + "\n")
        var = main_[(main_.tf.astype(str) == tf) & (main_.label.str.contains("var"))].copy()
        if len(var):
            base_ids = {}
            for r in var.itertuples():
                base = r.label.split("_var_")[0]
                b = main_[(main_.tf.astype(str) == tf) & (main_.label == base)]
                base_ids[r.id] = float(b.tv_net_pct.iloc[0]) if len(b) else np.nan
            var["base_net"] = var.id.map(base_ids)
            var["params_ko"] = var.params.map(lambda p: ", ".join(f"{k}={v:g}" for k, v in json.loads(p).items()))
            L.append(f"파라미터 변형 (기본값: 익절 3%, 손절 2%, 트레일링 2%, 샹들리에 2ATR, 시간 청산 4시간, 최대 보유 24시간):\n")
            L.append(md(var.sort_values(["label", "tv_net_pct"]), ["label_ko", "buy_ko", "sell_ko", "params_ko", "tv_trades", "tv_net_pct", "base_net", "tv_mdd_pct", "tv_pf"],
                        ["구분", "매수", "매도", "변형", "거래", "순수익 %", "기본값 순수익 %", "최대낙폭 %", "손익비"],
                        ["%s", "%s", "%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.2f"]) + "\n")
    if len(extra):
        L.append("## 7. 체결 규칙·정수 주 수 효과 (상위 조합 재실행)\n")
        L.append("1단계와 2단계의 차이를 분리하기 위해 상위 조합을 (a) **보유 연장**: 청산 봉 종가에 새 매수 신호가 같이 나면 팔지 않고 그 봉을 새 진입으로 삼아 보유(1단계는 같은 종가에 팔고 다시 샀는데, TradingView 엔진은 같은 ID의 청산 봉 재진입을 받지 않으므로 손으로 할 수 있는 등가 규칙으로 바꿈; 왕복 수수료는 아낌), (b) 초기 자본 ×1000(정수 주 절사 효과 제거), (c) 둘 다로 다시 돌렸다. 결과: 자본 ×1000은 어느 조합에서도 3%p 안쪽이라 정수 주 절사는 무시할 수 있고, 보유 연장은 종가 체결형 매도(PSAR·MACD·VWAP 전환, RSI2>90 등)가 들어간 조합에서 1단계 값을 거의 그대로 되살린다(15분봉 1위 +82% → +247%, 1시간봉 1위 +131% → +221%). 봉 안 체결형(샹들리에)만 쓰는 조합은 변화가 없다. 즉 **1단계의 높은 값은 \"매도 신호와 매수 신호가 겹치는 봉에서는 팔지 않는다\"는 규칙을 전제로 한 것**이고, 그 규칙을 쓰지 않으면 6절의 기본 2단계 값이 맞다.\n")
        rows = []
        import re as _re
        for r in extra.itertuples():
            base_label = _re.sub(r"_(sameBar_cap1000x|sameBar|cap1000x)$", "", r.label)
            b = main_[(main_.tf.astype(str) == str(r.tf)) & (main_.label == base_label)]
            rows.append(dict(tf=TF_KO[str(r.tf)], label_ko=label_ko(base_label), buy_ko=r.buy_ko, sell_ko=r.sell_ko, variant=r.label[len(base_label) + 1:], tv_trades=r.tv_trades, tv_net_pct=r.tv_net_pct, base_net=float(b.tv_net_pct.iloc[0]) if len(b) else np.nan, screen_net=r.screen_net, tv_mdd_pct=r.tv_mdd_pct))
        E = pd.DataFrame(rows)
        E["variant"] = E.variant.map({"sameBar": "보유 연장", "cap1000x": "자본 ×1000", "sameBar_cap1000x": "보유 연장 + 자본 ×1000"}).fillna(E.variant)
        L.append(md(E.sort_values(["tf", "label_ko", "variant"]), ["tf", "label_ko", "buy_ko", "sell_ko", "variant", "tv_trades", "tv_net_pct", "base_net", "screen_net", "tv_mdd_pct"],
                    ["시간봉", "구분", "매수", "매도", "변형", "거래", "순수익 %", "기본 2단계 %", "1단계 %", "최대낙폭 %"],
                    ["%s", "%s", "%s", "%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.0f"]) + "\n")
    tod = os.path.join(adir, "timeofday.csv")
    if os.path.exists(tod):
        T = pd.read_csv(tod)
        T = T[T.id < 1000]
        T["buy_ko"] = T.buy.map(kob)
        T["sell_ko"] = T.sell.map(kos)
        T["label_ko"] = T.label.map(label_ko)
        T = T[~T.label.str.contains("var")].sort_values("net_pct", ascending=False)
        L.append("## 8. 한국 시간으로 본 실행 가능성\n")
        L.append("확인된 전략의 거래 목록(Strategy Tester)을 한국 시간으로 바꿔, 사용자가 깨어 있는 미국 개장 직후(09:30~12:00 ET = 22:30/23:30~01:00/02:00 KST)에 진입하는 비율, 장 마감 전 1시간(15:00~16:00 ET = 새벽 04~06시 KST)에 청산하는 비율, 밤을 넘기는 비율을 쟀다. 진입이 개장 직후에 몰리고 청산이 장 마감 직전에 몰리는 전략은 손으로 하기 어렵고 알림·예약 주문이 필요하다.\n")
        L.append(md(T.head(40), ["tf", "label_ko", "buy_ko", "sell_ko", "trades", "net_pct", "entry_first150_pct", "exit_last60_pct", "overnight_pct", "median_hold_h", "ret_first150", "ret_other"],
                    ["시간봉", "구분", "매수", "매도", "거래", "순수익 %", "개장 2.5h 안 진입 %", "마감 1h 안 청산 %", "오버나이트 %", "보유 중앙값 h", "개장 진입 평균 %/회", "그 외 진입 평균 %/회"],
                    [lambda v: TF_KO.get(str(v), str(v)), "%s", "%s", "%s", "%d", "%.0f", "%.0f", "%.0f", "%.0f", "%.1f", "%.2f", "%.2f"]) + "\n")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print("written", out, len("\n".join(L)), "chars")


if __name__ == "__main__":
    main()
