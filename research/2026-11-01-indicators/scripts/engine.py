"""Indicator-rule backtester for SOXL / SOXS short-term trades on daily bars.

Decision point: close of day t (close-based conditions use data through t) or, for open-based
conditions (gaps), the open of day t+1. Every condition is a boolean array indexed by the signal day t.
Templates (how the trade is executed after a signal on day t):
  OC  : buy open t+1, sell close t+1          (day trade, no overnight)
  OO  : buy open t+1, sell open t+2           (24 h)
  CC  : buy close t,  sell close t+1          (needs action at the close)
  CO  : buy close t,  sell open t+1           (overnight only)
  O3C : buy open t+1, sell close t+3          (non-overlapping)
  O5C : buy open t+1, sell close t+5          (non-overlapping)
  SIG : buy open t+1 when the condition turns true, sell at the open after it turns false
Fees 0.25% per side. Instruments: long SOXL or long SOXS (bearish bet) on the same signal.
"""
import sys, site; sys.path.insert(0, site.getusersitepackages())
import os, itertools, numpy as np, pandas as pd

FEE = 0.0025
TEMPLATES = ["OC", "OO", "CC", "CO", "O3C", "O5C", "SIG"]
TEMPLATE_KO = {"OC": "다음날 시가→당일 종가", "OO": "다음날 시가→다다음날 시가", "CC": "종가→다음날 종가",
               "CO": "종가→다음날 시가(오버나이트)", "O3C": "다음날 시가→3일째 종가", "O5C": "다음날 시가→5일째 종가",
               "SIG": "조건 참이면 다음날 시가 매수, 거짓 되면 다음날 시가 매도"}

def net(pin, pout):
    return (pout / pin) * (1 - FEE) / (1 + FEE) - 1

# ---------- data ----------
def load(data_dir):
    rd = lambda n: pd.read_csv(os.path.join(data_dir, f"{n}_1d.csv"), index_col=0, parse_dates=True)
    soxl = rd("soxl"); idx = soxl.index
    soxs = rd("soxs").reindex(idx)
    soxx = rd("soxx").reindex(idx).ffill()
    vix = rd("vix").reindex(idx).ffill()
    return soxl, soxs, soxx, vix

# ---------- indicators ----------
def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n):
    d = s.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean(); ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)
def true_range(df):
    return pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1).max(axis=1)
def atr(df, n): return true_range(df).ewm(alpha=1 / n, adjust=False).mean()
def adx(df, n=14):
    up = df.high.diff(); dn = -df.low.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, mdi
def cci(df, n=20):
    tp = (df.high + df.low + df.close) / 3; m = tp.rolling(n).mean()
    md = (tp - m).abs().rolling(n).mean()
    return (tp - m) / (0.015 * md)
def stoch(df, n=14, d=3):
    ll = df.low.rolling(n).min(); hh = df.high.rolling(n).max()
    k = 100 * (df.close - ll) / (hh - ll)
    return k, k.rolling(d).mean()
def run_length(mask):
    """consecutive count of True ending at each position"""
    out = np.zeros(len(mask), dtype=int); c = 0
    for i, m in enumerate(mask):
        c = c + 1 if m else 0; out[i] = c
    return pd.Series(out, index=mask.index)

# ---------- conditions ----------
def build_conditions(soxl, soxx, vix):
    C, O, H, L, V = soxl.close, soxl.open, soxl.high, soxl.low, soxl.volume
    idx = soxl.index
    conds = {}
    def add(key, s, label, cat, open_based=False, pairs=True):
        conds[key] = dict(s=s.fillna(False).astype(bool).to_numpy(), label=label, cat=cat, open_based=open_based, pairs=pairs)
    for n in (5, 10, 20, 50, 200):
        m = sma(C, n)
        add(f"C>SMA{n}", C > m, f"종가 > {n}일 이평", "추세"); add(f"C<SMA{n}", C < m, f"종가 < {n}일 이평", "추세")
    for a, b in ((5, 20), (10, 50), (20, 50), (50, 200)):
        add(f"SMA{a}>SMA{b}", sma(C, a) > sma(C, b), f"{a}일 이평 > {b}일 이평", "추세")
        add(f"SMA{a}<SMA{b}", sma(C, a) < sma(C, b), f"{a}일 이평 < {b}일 이평", "추세")
    e9, e21 = ema(C, 9), ema(C, 21)
    add("EMA9>EMA21", e9 > e21, "EMA9 > EMA21", "추세"); add("EMA9<EMA21", e9 < e21, "EMA9 < EMA21", "추세")
    add("EMA9xUp", (e9 > e21) & (e9.shift() <= e21.shift()), "EMA9가 EMA21 상향 돌파(당일)", "추세")
    add("EMA9xDn", (e9 < e21) & (e9.shift() >= e21.shift()), "EMA9가 EMA21 하향 돌파(당일)", "추세")
    macd = ema(C, 12) - ema(C, 26); sig = ema(macd, 9); hist = macd - sig
    add("MACD>Sig", macd > sig, "MACD > 시그널", "추세"); add("MACD<Sig", macd < sig, "MACD < 시그널", "추세")
    add("MACD>0", macd > 0, "MACD > 0", "추세"); add("MACD<0", macd < 0, "MACD < 0", "추세")
    add("MACDhist↑", hist > hist.shift(), "MACD 히스토그램 상승", "추세"); add("MACDhist↓", hist < hist.shift(), "MACD 히스토그램 하락", "추세")
    add("MACDxUp", (macd > sig) & (macd.shift() <= sig.shift()), "MACD 골든크로스(당일)", "추세")
    add("MACDxDn", (macd < sig) & (macd.shift() >= sig.shift()), "MACD 데드크로스(당일)", "추세")
    ad, pdi, mdi = adx(soxl)
    add("ADX>25up", (ad > 25) & (pdi > mdi), "ADX>25 & +DI>-DI (상승 추세)", "추세")
    add("ADX>25dn", (ad > 25) & (mdi > pdi), "ADX>25 & -DI>+DI (하락 추세)", "추세")
    add("ADX<20", ad < 20, "ADX < 20 (횡보)", "변동성")
    hh20 = H.rolling(20).max().shift(); ll20 = L.rolling(20).min().shift()
    hh55 = H.rolling(55).max().shift(); ll55 = L.rolling(55).min().shift()
    add("C>HH20", C > hh20, "20일 신고가 돌파", "모멘텀"); add("C<LL20", C < ll20, "20일 신저가 이탈", "모멘텀")
    add("C>HH55", C > hh55, "55일 신고가 돌파", "모멘텀"); add("C<LL55", C < ll55, "55일 신저가 이탈", "모멘텀")
    r2, r14 = rsi(C, 2), rsi(C, 14)
    add("RSI2<10", r2 < 10, "RSI(2) < 10", "역추세"); add("RSI2<25", r2 < 25, "RSI(2) < 25", "역추세")
    add("RSI2>75", r2 > 75, "RSI(2) > 75", "모멘텀"); add("RSI2>90", r2 > 90, "RSI(2) > 90", "모멘텀")
    add("RSI14<30", r14 < 30, "RSI(14) < 30", "역추세"); add("RSI14<40", r14 < 40, "RSI(14) < 40", "역추세")
    add("RSI14>60", r14 > 60, "RSI(14) > 60", "모멘텀"); add("RSI14>70", r14 > 70, "RSI(14) > 70", "모멘텀")
    mb = sma(C, 20); sd = C.rolling(20).std(); ub, lb = mb + 2 * sd, mb - 2 * sd; pb = (C - lb) / (ub - lb)
    add("C<BBlo", C < lb, "종가 < 볼린저 하단(20,2)", "역추세"); add("C>BBup", C > ub, "종가 > 볼린저 상단(20,2)", "모멘텀")
    add("%B<0.2", pb < 0.2, "볼린저 %B < 0.2", "역추세"); add("%B>0.8", pb > 0.8, "볼린저 %B > 0.8", "모멘텀")
    k, d = stoch(soxl)
    add("StochK<20", k < 20, "스토캐스틱 %K(14) < 20", "역추세"); add("StochK>80", k > 80, "스토캐스틱 %K(14) > 80", "모멘텀")
    add("StochxUp", (k > d) & (k.shift() <= d.shift()), "스토캐스틱 %K가 %D 상향 돌파", "역추세")
    add("StochxDn", (k < d) & (k.shift() >= d.shift()), "스토캐스틱 %K가 %D 하향 돌파", "모멘텀")
    cc = cci(soxl); add("CCI<-100", cc < -100, "CCI(20) < -100", "역추세"); add("CCI>100", cc > 100, "CCI(20) > 100", "모멘텀")
    r = C.pct_change()
    add("ret<-5%", r < -0.05, "당일 -5% 이하 하락", "역추세"); add("ret<-8%", r < -0.08, "당일 -8% 이하 하락", "역추세")
    add("ret>+5%", r > 0.05, "당일 +5% 이상 상승", "모멘텀"); add("ret>+8%", r > 0.08, "당일 +8% 이상 상승", "모멘텀")
    dn = run_length(r < 0); up = run_length(r > 0)
    add("down2", dn >= 2, "2일 연속 하락", "역추세"); add("down3", dn >= 3, "3일 연속 하락", "역추세")
    add("up2", up >= 2, "2일 연속 상승", "모멘텀"); add("up3", up >= 3, "3일 연속 상승", "모멘텀")
    clv = (C - L) / (H - L)
    add("CLV<0.2", clv < 0.2, "저가 근처 마감(하위 20%)", "역추세"); add("CLV>0.8", clv > 0.8, "고가 근처 마감(상위 20%)", "모멘텀")
    dev = C / sma(C, 20) - 1
    add("dev<-10%", dev < -0.10, "20일 이평 대비 -10% 이하", "역추세"); add("dev>+10%", dev > 0.10, "20일 이평 대비 +10% 이상", "모멘텀")
    vm = sma(V, 20)
    add("Vol>1.5x", V > 1.5 * vm, "거래량 > 20일 평균 1.5배", "거래량"); add("Vol<0.7x", V < 0.7 * vm, "거래량 < 20일 평균 0.7배", "거래량")
    a14 = atr(soxl, 14) / C
    add("ATRhi", a14 > a14.rolling(100).median(), "ATR/가격 > 100일 중앙값(변동성 큼)", "변동성")
    add("ATRlo", a14 < a14.rolling(100).median(), "ATR/가격 < 100일 중앙값(변동성 작음)", "변동성")
    bw = (ub - lb) / mb
    add("BBsqueeze", bw < bw.rolling(100).quantile(0.2), "볼린저 밴드폭 100일 하위 20%(스퀴즈)", "변동성")
    vx = vix.close
    add("VIX>25", vx > 25, "VIX > 25", "변동성"); add("VIX<20", vx < 20, "VIX < 20", "변동성")
    add("VIX↑10%", vx.pct_change() > 0.10, "VIX 당일 +10% 이상", "변동성"); add("VIX↓10%", vx.pct_change() < -0.10, "VIX 당일 -10% 이하", "변동성")
    xc = soxx.close
    add("SOXX>SMA50", xc > sma(xc, 50), "SOXX > 50일 이평", "추세"); add("SOXX<SMA50", xc < sma(xc, 50), "SOXX < 50일 이평", "추세")
    add("SOXX>SMA200", xc > sma(xc, 200), "SOXX > 200일 이평", "추세"); add("SOXX<SMA200", xc < sma(xc, 200), "SOXX < 200일 이평", "추세")
    gap = O.shift(-1) / C - 1            # next day's opening gap, known at that open
    add("gap<-2%", gap < -0.02, "다음날 시가 갭 -2% 이하", "역추세", open_based=True)
    add("gap<-4%", gap < -0.04, "다음날 시가 갭 -4% 이하", "역추세", open_based=True)
    add("gap>+2%", gap > 0.02, "다음날 시가 갭 +2% 이상", "모멘텀", open_based=True)
    add("gap>+4%", gap > 0.04, "다음날 시가 갭 +4% 이상", "모멘텀", open_based=True)
    nd = pd.Series(idx.dayofweek, index=idx).shift(-1)   # weekday of day t+1 (the trade day for O templates)
    for w, name in enumerate(["월", "화", "수", "목", "금"]):
        add(f"{name}요일", nd == w, f"다음 거래일이 {name}요일", "달력", pairs=False)
    add("ALL", pd.Series(True, index=idx), "조건 없음(매일)", "기준", pairs=False)
    return conds

# ---------- trades ----------
def trades_for(sig, tpl, O, C):
    """sig: bool array over signal days t. returns arrays (entry_i, entry_p, exit_i, exit_p)"""
    n = len(sig); t = np.flatnonzero(sig)
    if tpl == "OC":
        t = t[t + 1 < n]; return t + 1, O[t + 1], t + 1, C[t + 1]
    if tpl == "OO":
        t = t[t + 2 < n]; return t + 1, O[t + 1], t + 2, O[t + 2]
    if tpl == "CC":
        t = t[t + 1 < n]; return t, C[t], t + 1, C[t + 1]
    if tpl == "CO":
        t = t[t + 1 < n]; return t, C[t], t + 1, O[t + 1]
    if tpl in ("O3C", "O5C"):
        h = 3 if tpl == "O3C" else 5
        ei, xi = [], []; last_exit = -1
        for s in t:
            if s + 1 > last_exit and s + h < n:
                ei.append(s + 1); xi.append(s + h); last_exit = s + h
        ei = np.array(ei, dtype=int); xi = np.array(xi, dtype=int)
        return ei, O[ei], xi, C[xi]
    if tpl == "SIG":
        s = sig.astype(np.int8); d = np.diff(np.r_[0, s, 0])
        starts = np.flatnonzero(d == 1); ends = np.flatnonzero(d == -1) - 1   # inclusive runs
        ei = starts + 1; xi = ends + 2
        ok = xi < n; ei, xi = ei[ok], xi[ok]
        return ei, O[ei], xi, O[xi]
    raise ValueError(tpl)

def evaluate(ei, ep, xi, xp, C, idx, is_mask, years, keep=False):
    n = len(ei)
    if n == 0: return None
    tr = net(ep, xp)
    lr = np.zeros(len(C))
    multi = (xi - ei).max() > 0 if n else False
    if not multi:
        np.add.at(lr, xi, np.log1p(tr))
    else:
        for a, pa, b, pb in zip(ei, ep, xi, xp):
            # mark to market at closes between entry and exit, fees at entry/exit
            path = np.empty(b - a + 1)
            prev = pa * (1 + FEE)
            for k, dday in enumerate(range(a, b + 1)):
                px = C[dday] if dday < b else pb * (1 - FEE)
                path[k] = np.log(px / prev); prev = px
            lr[a:b + 1] += path
    eq = np.exp(np.cumsum(lr)); total = eq[-1] - 1
    dd = (eq / np.maximum.accumulate(eq) - 1).min()
    dr = np.expm1(lr); sh = dr.mean() / dr.std() * np.sqrt(252) if dr.std() > 0 else 0.0
    pos = tr[tr > 0].sum(); neg = -tr[tr < 0].sum()
    yrs = pd.Series(lr, index=idx).groupby(idx.year).sum()
    extra = dict(lr=lr, tr=tr, ei=ei, xi=xi) if keep else {}
    return dict(**extra, n=n, win=round(100 * (tr > 0).mean(), 1), avg=round(100 * tr.mean(), 2), med=round(100 * np.median(tr), 2),
                pf=round(pos / neg, 2) if neg > 0 else np.inf, total=round(100 * total, 1),
                cagr=round(100 * ((1 + total) ** (1 / years) - 1), 1), mdd=round(100 * dd, 1), sharpe=round(sh, 2),
                tstat=round(tr.mean() / tr.std() * np.sqrt(n), 2) if n > 1 and tr.std() > 0 else 0.0,
                expo=round(100 * (lr != 0).mean(), 1),
                is_total=round(100 * (np.exp(lr[is_mask].sum()) - 1), 1), oos_total=round(100 * (np.exp(lr[~is_mask].sum()) - 1), 1),
                pos_years=int((yrs > 0).sum()), worst_year=round(100 * (np.exp(yrs.min()) - 1), 1),
                yearly={int(y): round(100 * (np.exp(v) - 1), 1) for y, v in yrs.items()})

class Backtester:
    def __init__(self, data_dir, start="2016-10-24", end="2026-10-30", is_end="2021-10-29"):
        soxl, soxs, soxx, vix = load(data_dir)
        self.conds = build_conditions(soxl, soxx, vix)
        m = (soxl.index >= start) & (soxl.index <= end)
        self.idx = soxl.index[m]
        self.years = (self.idx[-1] - self.idx[0]).days / 365.25
        self.is_mask = (self.idx <= is_end)
        self.soxl = soxl[m]; self.soxs = soxs[m]; self.soxx = soxx[m]; self.vix = vix[m]; self.full = soxl
        self.px = {"SOXL": (soxl.open.to_numpy()[m], soxl.close.to_numpy()[m]),
                   "SOXS": (soxs.open.to_numpy()[m], soxs.close.to_numpy()[m])}
        for k in self.conds: self.conds[k]["s"] = self.conds[k]["s"][m]
    def signal(self, keys):
        s = np.ones(len(self.idx), dtype=bool)
        for k in keys: s &= self.conds[k]["s"]
        return s
    def run(self, keys, tpl, inst, keep=False):
        if tpl in ("CC", "CO") and any(self.conds[k]["open_based"] for k in keys): return None
        return self.run_sig(self.signal(keys), tpl, inst, keep)
    def run_sig(self, sig, tpl, inst, keep=False):
        O, C = self.px[inst]
        ei, ep, xi, xp = trades_for(np.asarray(sig, dtype=bool), tpl, O, C)
        return evaluate(ei, ep, xi, xp, C, self.idx, self.is_mask, self.years, keep)
