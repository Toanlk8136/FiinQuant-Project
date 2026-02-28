from FiinQuantX import FiinSession
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
import json

# Điền thông tin đăng nhập
username = "toanluukhanh1999@gmail.com"
password = "tua9haha"

# Khởi tạo session và đăng nhập
client = FiinSession(username=username, password=password).login()

# Kiểm tra kết nối thành công
print("Đăng nhập thành công:", type(client))

from_date = "2026-02-06"
to_date   = "2026-02-13"

VIN = ["VIC", "VHM", "VRE", "VPL"]
ETF_PREFIX = ('FU', 'FUC', 'E1')

# VNINDEX universe để tính tổng liquidity + total market cap theo ngày
tickers_mkt = [t for t in client.TickerList(ticker="VNINDEX") if not t.startswith(ETF_PREFIX)]
print("Total tickers market:", len(tickers_mkt))

# =========================
# 1) FETCH OVERVIEW: MARKET (1 lần)
# =========================
raw_mkt = client.PriceStatistics().get_overview(
    tickers=tickers_mkt,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)
mkt = pd.DataFrame(raw_mkt)
mkt["date"] = pd.to_datetime(mkt["timestamp"]).dt.normalize()

mkt["totalMatchValue"] = pd.to_numeric(mkt["totalMatchValue"], errors="coerce")
mkt["marketCap"]       = pd.to_numeric(mkt["marketCap"], errors="coerce")
mkt = mkt.dropna(subset=["date","ticker","totalMatchValue","marketCap"])

mkt_daily = (
    mkt.groupby("date")
       .agg(
           market_liquidity=("totalMatchValue","sum"),
           market_cap_total=("marketCap","sum"),
       )
       .reset_index()
)

# =========================
# 2) FETCH OVERVIEW: VIN (marketCap + value + %change)
# =========================
raw_vin = client.PriceStatistics().get_overview(
    tickers=VIN,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)
vin = pd.DataFrame(raw_vin)
vin["date"] = pd.to_datetime(vin["timestamp"]).dt.normalize()

vin["totalMatchValue"] = pd.to_numeric(vin["totalMatchValue"], errors="coerce")
vin["marketCap"]       = pd.to_numeric(vin["marketCap"], errors="coerce")
vin["percentPriceChange"] = pd.to_numeric(vin["percentPriceChange"], errors="coerce")

vin = vin.dropna(subset=["date","ticker","totalMatchValue","marketCap","percentPriceChange"])

# =========================
# 3) FETCH CLOSE: VIN (để có cột close như ảnh)
# =========================
price_raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=VIN,
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date=from_date,
    to_date=to_date
).get_data()

px = pd.DataFrame(price_raw)
px["date"] = pd.to_datetime(px["timestamp"]).dt.normalize()
px = px[["date","ticker","close"]].copy()

# =========================
# 4) MERGE + CALC METRICS
# =========================
out = (
    vin.merge(px, on=["date","ticker"], how="left")
       .merge(mkt_daily, on="date", how="left")
)

# ratios
out["liq_vs_market"] = out["totalMatchValue"] / out["market_liquidity"]
out["liq_vs_mcap"]   = out["totalMatchValue"] / out["marketCap"]

# contribution proxy (giống số dạng 0.x trong ảnh)
# = (mcap_share * pct_change) * 100
out["contribution_point"] = (out["marketCap"] / out["market_cap_total"]) * out["percentPriceChange"] * 100

# format cột như ảnh
out = out.rename(columns={
    "percentPriceChange": "price_change_pct"
})

# sort
out = out.sort_values(["date","ticker"]).reset_index(drop=True)

# =========================
# 5) EXPORT EXCEL
# =========================
output_file = "VIN_pack_liq_mcap_contribution.xlsx"
out[[
    "date",
    "ticker",
    "close",
    "price_change_pct",
    "marketCap",
    "totalMatchValue",
    "liq_vs_market",
    "liq_vs_mcap",
    "contribution_point"
]].to_excel(output_file, index=False)

print("DONE ->", output_file)
print(out.head(10))