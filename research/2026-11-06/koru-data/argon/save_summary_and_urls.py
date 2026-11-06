#!/usr/bin/env python3
import json
import os
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"

# 1. Verify 2026 YTD out-of-sample beta (2026-01-01 ~ 2026-11-04, BEFORE 2026-11-05!)
ewy = yf.Ticker("EWY").history(period="10y", interval="1d")
sox = yf.Ticker("^SOX").history(period="10y", interval="1d")
koru = yf.Ticker("KORU").history(period="10y", interval="1d")

df = pd.DataFrame({
    "ewy_oc": (ewy["Close"] / ewy["Open"] - 1).tz_localize(None) * 100,
    "sox_oc": (sox["Close"] / sox["Open"] - 1).tz_localize(None) * 100,
    "koru_oc": (koru["Close"] / koru["Open"] - 1).tz_localize(None) * 100,
}).dropna()

df_pre26 = df.loc[:"2025-12-31"]
df_2026_oos = df.loc["2026-01-01":"2026-11-04"]
df_2026_all = df.loc["2026-01-01":"2026-11-05"]

for name, sub in [("2016-2025 (Pre-2026)", df_pre26), ("2026 OOS (thru 11/04)", df_2026_oos), ("2026 All (thru 11/05)", df_2026_all)]:
    b, a = np.polyfit(sub["sox_oc"], sub["ewy_oc"], 1)
    r2 = sub["sox_oc"].corr(sub["ewy_oc"]) ** 2
    bk, ak = np.polyfit(sub["sox_oc"], sub["koru_oc"], 1)
    print(f"{name:24s} N={len(sub):4d} | EWY_OC = {a:+.3f} + {b:.3f}*SOX_OC (R2={r2:.3f}) | KORU_OC beta={bk:.3f}")

# Check SOXX split-adjusted return on 11/5!
# Note: 11/4 SOXX pre-split close = 450.41 -> 3-for-1 split adjusted prev close = 450.41 / 3 = 150.1367
# 11/5 SOXX close = 131.90 -> 131.90 / 150.1367 - 1 = -12.1467%
print(f"\nSOXX 3-for-1 split check: 450.41/3 = {450.41/3:.4f}, 11/5 O=143.08 ({(143.08/(450.41/3)-1)*100:+.2f}%), C=131.90 ({(131.90/(450.41/3)-1)*100:+.2f}%)")
print(f"^SOX 11/4 C=10268.65 -> 11/5 O=9806.31 ({(9806.31/10268.65-1)*100:+.2f}%), H=9838.13, L=8997.39, C=9011.14 ({(9011.14/10268.65-1)*100:+.2f}%)")

# 2. Check Codex strict pre-expiry bar vs exact minute bar & Yahoo raw 5m bar
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/KORU?range=5d&interval=5m&includePrePost=true", headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    raw5 = json.loads(resp.read().decode("utf-8"))
res5 = raw5["chart"]["result"][0]
ts5 = res5["timestamp"]
q5 = res5["indicators"]["quote"][0]
import pytz
kst = pytz.timezone("Asia/Seoul")
print("\n=== Yahoo Raw 5m bars around 2026-11-06 07:20 ~ 07:45 KST ===")
for t, o, h, l, c, v in zip(ts5, q5["open"], q5["high"], q5["low"], q5["close"], q5["volume"]):
    dt = pd.Timestamp(t, unit="s", tz="UTC").tz_convert(kst)
    if pd.Timestamp("2026-11-06 07:20:00", tz=kst) <= dt <= pd.Timestamp("2026-11-06 07:45:00", tz=kst):
        print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S %Z')} | O={o} H={h} L={l} C={c} V={v}")

# 3. Resolve redirect URLs from search_web for clean citations
redirect_urls = {
    "chosun_1105": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFtmVYaDJ0yIcFYbOKCvovq12qyYTs8Zm49H8Hk8Kr88qv8Z9ETVO4MLVctD22XsftLWc62ttTLT6EwDZygP14Fp_h8-s1gHdsSWRWlRE-UIIelJtZXY24qKKtgirlpVlpmc2YQ0i0zz9NKoLk4pKztoUAgkK_DqxHS2zNAwRM7IZw=",
    "etnews_1105": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhFqX7is7MVREhamOl5scvD1lElK_7UxMFlHHdRW34WSibTx80xaiRbtpzwrFpaz46vjorSrfqnzyOpuFcTIKVg6BYPc6hvj_0eTLboQjEOmU60LLN_Wfn-nGu",
    "cnn_1105": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFgFYqWYs0_rkHXc9XdgnJCM7t1XnX2cj607YdVRJ04DkGV8iqHnSYynpzY010gusycmQ2ONvmGKsyKXc8U3ZguXPbLMFfFXGdrijsAntIHJMcdUzL36rfE4XS4pfeKO4WNdZSzp3ltZNL7xveFlhdhbVhtEGGTX_4=",
    "fnnews_vix_1106": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpqVOabGFML4V5rz8M-x0z3Jg24_TG7aLZ44n_CvrX-OAlLuAUnAby0zqvqcW2gxRK4XyDcou-gZYQJmF0j6Q24O9qyseZJ-aZb4B-OUwkxQ7qjPhZon_cjC-OxfZiIPeRlbg=",
    "yna_us_1106": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjmpG6IGQxRZy2zJYHT4T3F87F5XdUItC5BaOdrXzkSpO6Z2bsCG29TXeyA2dxqsdpo-090phEkcot0NG-0Xq21N5m5t3sS4MP87ez37EF-W_ESct5mF9mUAdt5XGFAkXp2fdmgag==",
    "yna_cb_1106": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEl0mZ-PKATHkfg1N8RzYZZ_HQl37dgieTErQBiLCBtxHp2XXJzdXsRR2cleyaVXU6L_UojYInxpmh7rX0n_kpw79YpKcwRdg6xYxXkYA30bJ0KI7Vusf5iONUKwglknnlnDj8zow==",
    "ytn_cb_1106": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGmRLYK0f2EnMN3ozWfldVJ0thGc3Se7PcAn5xhXKFpinXW043YPHP7KA50pOVz6QFctkB6U1tCxejj4fiY4qVNJio6jwn5d7FJ2aURSKjN7EARqMIFLNE9B99RlXHTYsrAZqhjrmZq",
    "einfomax_sox_1106": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTk8-VJ4DPkGo6CosgvpR9NaXnC9JzYFFnbf6fi5fomigEgOEGtzLdn0xtjt7p0mW54lLX3CMsXMBa27hZy30uHLVlUXEd1pHuukiYuPmg5_JNUWSAu6M-0RvU6tgf3U7A03JHOUOWwGcwdQb06DhhbUc8tEY=",
    "investing_claims": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGKzZ9btO7xSQ8MGCihV-QrIjQ--i39qzpYTocxc7kSeIGbl3xKGfHE8lsAdryn3FRvC9Hzih0SOu97-x3VwLGDCVzM4fY8VuJtPU4vD0iWa24c2WobmTULM6AHv6dzRJw3laV2o3B-CifTmOwFYnQF3DKn7LW60sZFx4pcM4aDzmYyB5iBXCAF05RjZSiNoeBSvFgjyU4CKfbdWrknkeKmFyIsGyiSsuZ0yI3ztsA=",
    "tradingview_boe": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHtJxj7HhSfBhqwtribdH-7basV-W9V8zKZ-JY0rReCA7x04KLUrVaRtdepZZsWylMT6PPdfXGlgUbhd1ECI7GW21ZNHC648WKHLvROPeMZFR8mcx-qSd9-xA6apLeLOCPIwNqITvSTeZa_xpIz3sGAFq8-sgqy36L-pKY53mGJKq5G6t61caWvAAwn-ccUW3X5BADVXBfUz8V7uXNUDYVhLdyB5tLuBgurK9r538DgpgQ5sw==",
}
print("\n=== Resolved URLs ===")
resolved = {}
for k, u in redirect_urls.items():
    try:
        req = urllib.request.Request(u, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=6) as r:
            resolved[k] = r.geturl()
            print(f"  {k}: {r.geturl()}")
    except Exception as e:
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r:
                resolved[k] = r.geturl()
                print(f"  {k}: {r.geturl()}")
        except Exception as e2:
            print(f"  {k}: ERR {e2}")

with open(os.path.join(OUT_DIR, "resolved_urls.json"), "w", encoding="utf-8") as f:
    json.dump(resolved, f, ensure_ascii=False, indent=2)
