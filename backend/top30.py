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

tickers = client.TickerList(ticker="VNINDEX")
ETF_PREFIX = ('FU', 'FUC', 'E1')

tickers = [
    t for t in tickers
    if not t.startswith(ETF_PREFIX)]
# 3. FETCH OVERVIEW DATA (THANH KHOẢN)
# =========================
raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date="2026-02-09",
    to_date="2026-02-13"
)

df = pd.DataFrame(raw)
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

# =========================
# 4. FETCH GIÁ ĐÓNG CỬA & TÍNH % GIÁ NGÀY
# =========================
price_raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date="2026-02-06",
    to_date="2026-02-13"
).get_data()

price_df = pd.DataFrame(price_raw)
price_df['date'] = pd.to_datetime(price_df['timestamp']).dt.normalize()
price_df = price_df.sort_values(['ticker', 'date'])

price_df['daily_pct_change'] = (
    price_df
    .groupby('ticker')['close']
    .pct_change()
) * 100

# =========================
# 5. TOP 30 THANH KHOẢN MỖI PHIÊN
# =========================
top30_each_day = (
    df
    .sort_values(['date', 'totalMatchValue'], ascending=[True, False])
    .groupby('date')
    .head(30)
    [['date', 'ticker', 'totalMatchValue', 'marketCap']]
)

# =========================
# 6. GHÉP % GIÁ NGÀY
# =========================
top30_each_day = top30_each_day.merge(
    price_df[['ticker', 'date', 'daily_pct_change']],
    on=['ticker', 'date'],
    how='left'
)

# =========================
# 7. XUẤT EXCEL
# =========================
top30_each_day.to_excel(
    "top30_liquidity.xlsx",
    index=False
)

