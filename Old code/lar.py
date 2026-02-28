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
    if not t.startswith(ETF_PREFIX)
]

raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date="2026-01-22",
    to_date = "2026-01-23"
)

df = pd.DataFrame(raw)
print(df.columns)
print(df.head())
#3️⃣ Chuẩn hoá ngày giao dịch
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()
#4️⃣ Định nghĩa mã tăng
df['is_adv'] = df['percentPriceChange'] > 0
#5️⃣ Thanh khoản TOÀN thị trường (theo ngày)
total_liquidity = (
    df
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index()
    .rename(columns={'totalMatchValue': 'total_liquidity'})
)
#6️⃣ Thanh khoản MÃ TĂNG (theo ngày)
adv_liquidity = (
    df[df['is_adv']]
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index()
    .rename(columns={'totalMatchValue': 'adv_liquidity'})
)
#7️⃣ Ghép & tính Liquidity Ratio
liquidity_ratio = total_liquidity.merge(
    adv_liquidity,
    on='date',
    how='left'
)

liquidity_ratio['adv_liquidity'] = liquidity_ratio['adv_liquidity'].fillna(0)

liquidity_ratio['adv_liquidity_ratio'] = (
    liquidity_ratio['adv_liquidity'] /
    liquidity_ratio['total_liquidity']
)

liquidity_ratio = liquidity_ratio.sort_values('date')

print(adv_liquidity.head())