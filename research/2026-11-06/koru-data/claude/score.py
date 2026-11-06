"""KORU 11/5 회차 3개 노트 채점·국면 분해 (Claude Fable Max).
입력: m1_*.csv (fetch_1m.py 산출). 출력: 표준출력 + score.json
실행: python3 research/2026-11-06/koru-data/claude/score.py
"""
import json
from pathlib import Path
import pandas as pd

D = Path(__file__).resolve().parent
PREV_CLOSE = 10.43

def load(n):
    df = pd.read_csv(D / f"m1_{n}.csv", index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("Asia/Seoul")
    return df

k = load("KORU")
NOTES = {
    "Antigravity Argon High": dict(base_t="2026-11-05 07:31", base=10.58, exp_t="2026-11-06 07:31", up=0.44, up_close=0.51),
    "Codex Astra Max":        dict(base_t="2026-11-05 07:33", base=10.60, exp_t="2026-11-06 07:33", up=0.45, up_close=0.50),
    "Claude Fable Max":       dict(base_t="2026-11-05 07:38", base=10.62, exp_t="2026-11-06 07:40", up=0.45, up_close=0.55),
}
out = {}
for name, n in NOTES.items():
    bb = k.loc[pd.Timestamp(n["base_t"], tz="Asia/Seoul")]; eb = k.loc[pd.Timestamp(n["exp_t"], tz="Asia/Seoul")]   # 그 분의 1분봉 한 행
    prevbar = k.loc[:pd.Timestamp(n["exp_t"], tz="Asia/Seoul") - pd.Timedelta(minutes=1)].iloc[-1]
    px = float(eb["Close"])
    win = k.loc[n["base_t"]:n["exp_t"]]
    above = int((win["Close"] > n["base"]).sum())
    r = dict(base_bar=[float(bb[c]) for c in ("Open", "High", "Low", "Close")],
             expiry_bar=[float(eb[c]) for c in ("Open", "High", "Low", "Close")],
             prev_min_close=float(prevbar["Close"]), expiry_price=px,
             chg_vs_base=round((px / n["base"] - 1) * 100, 2), chg_vs_close=round((px / PREV_CLOSE - 1) * 100, 2),
             bars=len(win), bars_above_base=above, last_above_base=str(win.index[win["Close"] > n["base"]].max()),
             win_high=float(win["High"].max()), win_high_t=str(win["High"].idxmax()),
             win_low=float(win["Low"].min()), win_low_t=str(win["Low"].idxmin()),
             brier_base=round(n["up"] ** 2, 4), brier_close=round(n["up_close"] ** 2, 4))
    out[name] = r
    print(f"== {name}: base {n['base']} @ {n['base_t']} bar OHLC {r['base_bar']}")
    print(f"   expiry {n['exp_t']} bar OHLC {r['expiry_bar']} prev-min close {r['prev_min_close']}")
    print(f"   {n['base']} -> {px}: {r['chg_vs_base']:+.2f}% vs base, {r['chg_vs_close']:+.2f}% vs close 10.43")
    print(f"   bars {r['bars']}, above base {above} (last {r['last_above_base']}), high {r['win_high']} @ {r['win_high_t']}, low {r['win_low']} @ {r['win_low_t']}")
    print(f"   Brier base {r['brier_base']}, close {r['brier_close']}")

# 선(재검토선·시나리오 경계)이 처음 깨진 시각 (1분봉 종가 기준 / 저가 기준)
w = k.loc["2026-11-05 07:31":"2026-11-06 07:40"]
lines = {"10.43 정규장 종가": 10.43, "10.23 (11/4 정규장 저가 10.225)": 10.225, "10.07 Codex 하락 재개 경계": 10.07,
         "10.03 (11/4 프리마켓 저가)": 10.03, "10.00": 10.00, "9.95 Argon 최하 구간 상단": 9.95, "9.60 Claude C/D 경계": 9.60,
         "9.20 Codex 대표 하단": 9.20, "9.10 Argon 범위 하단": 9.10, "8.80 Claude 전체 범위 하단": 8.80, "8.00": 8.0, "7.00": 7.0}
print("== 선 이탈 최초 시각 (저가 기준 / 종가 기준)")
brk = {}
for lab, lv in lines.items():
    lo = w.index[w["Low"] < lv]; cl = w.index[w["Close"] < lv]
    brk[lab] = [str(lo.min()) if len(lo) else None, str(cl.min()) if len(cl) else None]
    print(f"   {lab:38s} low<{lv}: {brk[lab][0]}  close<{lv}: {brk[lab][1]}")
out["line_breaks"] = brk

# 국면 분해
PH = [("① 기준 직후·넥스트레이드 프리마켓·코스피 개장 (애프터마켓)", "2026-11-05 07:38", "2026-11-05 09:59"),
      ("③ 미국 프리마켓", "2026-11-05 18:00", "2026-11-05 23:29"),
      ("④-a 미국 정규장 첫 90분", "2026-11-05 23:30", "2026-11-06 00:59"),
      ("④-b 반등 시도", "2026-11-06 01:00", "2026-11-06 01:59"),
      ("④-c 오후 하락", "2026-11-06 02:00", "2026-11-06 04:59"),
      ("④-d 마지막 1시간", "2026-11-06 05:00", "2026-11-06 05:59"),
      ("④ 미국 정규장 전체", "2026-11-05 23:30", "2026-11-06 05:59"),
      ("⑤ 애프터마켓·만기", "2026-11-06 06:00", "2026-11-06 07:40"),
      ("⑥ 만기 이후", "2026-11-06 07:41", "2026-11-06 09:59")]
print("== 국면")
ph = []
for lab, a, b in PH:
    s = k.loc[a:b]
    if s.empty: continue
    row = dict(phase=lab, start=str(s.index[0]), end=str(s.index[-1]), open=float(s["Open"].iloc[0]), close=float(s["Close"].iloc[-1]),
               chg=round((s["Close"].iloc[-1] / s["Open"].iloc[0] - 1) * 100, 2), high=float(s["High"].max()), high_t=str(s["High"].idxmax())[5:16],
               low=float(s["Low"].min()), low_t=str(s["Low"].idxmin())[5:16], vol=int(s["Volume"].sum()))
    ph.append(row)
    print(f"   {lab}: {row['open']} -> {row['close']} ({row['chg']:+.2f}%) high {row['high']} @ {row['high_t']} low {row['low']} @ {row['low_t']} vol {row['vol']:,}")
out["phases"] = ph

# 프리마켓 첫 체결들
print("== 프리마켓 첫 15분 (11/5 18:00~18:15 KST)")
print(k.loc["2026-11-05 18:00":"2026-11-05 18:15"].round(3).to_string())
print("== 애프터마켓 마지막 (11/5 09:50~10:00 KST)")
print(k.loc["2026-11-05 09:50":"2026-11-05 10:01"].round(3).to_string())
print("== 정규장 개장 직후·마감 직전")
print(k.loc["2026-11-05 23:28":"2026-11-05 23:36"].round(3).to_string())
print(k.loc["2026-11-06 05:54":"2026-11-06 06:03"].round(3).to_string())
json.dump(out, open(D / "score.json", "w"), ensure_ascii=False, indent=1)
