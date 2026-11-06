"""네이버 금융 모바일 API에서 코스피 투자자별 일별 순매수(억원)를 모은다 (Claude Fable Max).
https://m.stock.naver.com/api/index/KOSPI/trend?bizdate=YYYYMMDD → {personalValue, foreignValue, institutionalValue}
대상: 2025-01-02 ~ 2026-11-05 코스피 거래일. 출력: kospi_investor_flows.csv
실행: python3 fetch_flows.py
"""
import json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd

D = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
ks = pd.read_pickle(D / "hist" / "d_KS11.pkl")
days = [d.strftime("%Y%m%d") for d in ks.index if "2025-01-01" <= d.strftime("%Y-%m-%d") <= "2026-11-04"] + ["20261105"]

def num(s):
    return int(str(s).replace(",", "").replace("+", "")) if s not in (None, "") else None

def get(day):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://m.stock.naver.com/api/index/KOSPI/trend?bizdate={day}", headers=UA), timeout=10) as r:
                d = json.load(r)
            if d.get("bizdate") != day:
                return day, None, None, None
            return day, num(d.get("personalValue")), num(d.get("foreignValue")), num(d.get("institutionalValue"))
        except Exception:  # noqa
            time.sleep(1 + i)
    return day, None, None, None

with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(get, days))
df = pd.DataFrame(rows, columns=["date", "individual", "foreign", "institution"]).set_index("date")
df.to_csv(D / "kospi_investor_flows.csv")
print("fetched_at_kst", pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M:%S"), "rows", len(df), "missing", int(df["foreign"].isna().sum()))
print(df.tail(12).to_string())
