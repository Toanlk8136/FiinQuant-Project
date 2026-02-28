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

from_date="2026-01-22",
to_date="2026-01-23"

raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

df = pd.DataFrame(raw)

df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

total_liquidity = (
    df
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index(name='total_liquidity')
)

top30_liquidity = (
    df
    .sort_values(['date', 'totalMatchValue'], ascending=[True, False])
    .groupby('date')
    .head(30)
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index(name='top30_liquidity')
)

tci = total_liquidity.merge(
    top30_liquidity,
    on='date',
    how='left'
)

tci['TCI'] = tci['top30_liquidity'] / tci['total_liquidity']
tci = tci.sort_values('date')

print(tci.tail())

