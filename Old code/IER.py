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
tickers = [t for t in tickers if not t.startswith(ETF_PREFIX)]

print("Số mã:", len(tickers))

from_date="2026-01-22"
to_date="2026-01-23"

vnindex_price = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VNINDEX"],
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date=from_date,
    to_date=to_date
).get_data()

vnindex_df = pd.DataFrame(vnindex_price)
vnindex_df['date'] = pd.to_datetime(vnindex_df['timestamp']).dt.normalize()
vnindex_df = vnindex_df.sort_values('date')

vnindex_df['index_change'] = (
    vnindex_df['close'] - vnindex_df['close'].shift(1)
)

# 5. LẤY TOTAL MATCHED VALUE TOÀN THỊ TRƯỜNG
# =========================
raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

df = pd.DataFrame(raw)
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

total_value = (
    df
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index(name='total_matched_value')
)

# =========================
# 6. GHÉP & TÍNH IER (SCALE THEO NGHÌN TỶ)
# =========================
ier = vnindex_df.merge(
    total_value,
    on='date',
    how='inner'
)

# IER = points per trillion VND
ier['IER'] = (
    ier['index_change'].abs() /
    (ier['total_matched_value'] / 1e12)
)

ier = ier.sort_values('date')

print(ier.tail())



