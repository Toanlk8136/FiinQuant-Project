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

# PARAMS
# =========================
from_date = "2026-02-06"   # để có T-1 cho 18/2
to_date   = "2026-02-13"

VIN = ["VIC", "VHM", "VRE", "VPL"]
ETF_PREFIX = ('FU', 'FUC', 'E1')

tickers = [t for t in client.TickerList(ticker="VNINDEX") if not t.startswith(ETF_PREFIX)]
print("Total tickers:", len(tickers))

# =========================
# 1) VNINDEX CLOSE & CHANGE (POINTS)
# =========================
vn_raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VNINDEX"],
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date=from_date,
    to_date=to_date
).get_data()

vn = pd.DataFrame(vn_raw)
vn["date"] = pd.to_datetime(vn["timestamp"]).dt.normalize()
vn = vn.sort_values("date")
vn["index_change"] = vn["close"] - vn["close"].shift(1)
vn = vn[["date", "index_change"]].copy()

# =========================
# 2) STOCK PRICE (% CHANGE) - ALL TICKERS (đúng logic code anh)
# =========================
price_raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date=from_date,
    to_date=to_date
).get_data()

price = pd.DataFrame(price_raw)
price["date"] = pd.to_datetime(price["timestamp"]).dt.normalize()
price = price.sort_values(["ticker", "date"])
price["price_change_pct"] = price.groupby("ticker")["close"].pct_change()   # decimal: 0.011 = 1.1%
price = price[["date", "ticker", "close", "price_change_pct"]].copy()

# =========================
# 3) OVERVIEW (MCAP + LIQ) - ALL TICKERS
# =========================
ov_raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

ov = pd.DataFrame(ov_raw)
ov["date"] = pd.to_datetime(ov["timestamp"]).dt.normalize()
ov["marketCap"] = pd.to_numeric(ov["marketCap"], errors="coerce")
ov["totalMatchValue"] = pd.to_numeric(ov["totalMatchValue"], errors="coerce")
ov = ov[["date", "ticker", "marketCap", "totalMatchValue"]].copy()

# =========================
# 4) MERGE ALL -> DF (ALL TICKERS) để tính scale chuẩn
# =========================
df = (
    price.merge(ov, on=["date", "ticker"], how="left")
)
df = df.dropna(subset=["price_change_pct", "marketCap", "totalMatchValue"]).copy()

# =========================
# 5) CONTRIBUTION (PROXY) + SCALE theo VNINDEX index_change
# =========================
df["total_mcap"] = df.groupby("date")["marketCap"].transform("sum")
df["weight_mcap"] = df["marketCap"] / df["total_mcap"]
df["raw_contribution"] = df["weight_mcap"] * df["price_change_pct"]

scale = (
    df.groupby("date")["raw_contribution"]
      .sum()
      .reset_index(name="raw_sum")
      .merge(vn, on="date", how="left")
)

scale["scale"] = np.where(scale["raw_sum"] == 0, np.nan, scale["index_change"] / scale["raw_sum"])

df = df.merge(scale[["date", "scale"]], on="date", how="left")
df["contribution_point"] = df["raw_contribution"] * df["scale"]

# =========================
# 6) LIQUIDITY SHARE + TURNOVER
# =========================
df["total_liquidity"] = df.groupby("date")["totalMatchValue"].transform("sum")
df["liq_vs_market"] = df["totalMatchValue"] / df["total_liquidity"]     # share theo ngày
df["liq_vs_mcap"]   = df["totalMatchValue"] / df["marketCap"]           # turnover

# =========================
# 7) FILTER VIN ONLY + EXPORT (format giống ảnh)
# =========================
vin_out = df[df["ticker"].isin(VIN)].copy()
vin_out = vin_out.sort_values(["date", "ticker"]).reset_index(drop=True)

# nếu anh muốn price_change_pct hiển thị dạng % (1.10%) trong Excel:
# vin_out["price_change_pct"] = vin_out["price_change_pct"]  # giữ decimal, Excel format % sẽ ra 1.10%
# hoặc nếu muốn số 1.10 (không phải 0.011) thì:
# vin_out["price_change_pct"] = vin_out["price_change_pct"] * 100

output_file = "VIN_contribution_scaled_to_VNINDEX.xlsx"
vin_out[[
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
print(vin_out.head(20))