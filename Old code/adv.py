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

data = client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=["open","high","low","close","volume"],
    adjusted=True,
    by="1d",
    from_date="2026-01-22",
    to_date="2026-01-23"
).get_data()

df = data.copy()

date_col = None
for col in ['date', 'tradingDate', 'timestamp', 'time']:
    if col in df.columns:
        date_col = col
        break

if date_col is None:
    raise Exception(f"Không tìm thấy cột ngày. Columns hiện có: {df.columns}")

df['date'] = pd.to_datetime(df[date_col])
df = df.sort_values(['ticker', 'date'])

# =========================
# 2. So sánh close hôm nay vs hôm trước
# =========================
df['prev_close'] = df.groupby('ticker')['close'].shift(1)
df = df.dropna(subset=['prev_close'])

# =========================
# 3. Gán trạng thái ADV / DEC / UNCH
# =========================
df['status'] = 'UNCH'
df.loc[df['close'] > df['prev_close'], 'status'] = 'ADV'
df.loc[df['close'] < df['prev_close'], 'status'] = 'DEC'

# =========================
# 4. Đếm breadth theo ngày
# =========================
breadth = (
    df
    .groupby(['date', 'status'])
    .size()
    .unstack(fill_value=0)
    .reset_index()
)

# đảm bảo đủ cột
for col in ['ADV', 'DEC', 'UNCH']:
    if col not in breadth.columns:
        breadth[col] = 0

breadth = breadth.rename(columns={
    'ADV': 'A',
    'DEC': 'D',
    'UNCH': 'U'
})

# =========================
# 5. Tính Advance Ratio
# =========================
breadth['total'] = breadth['A'] + breadth['D'] + breadth['U']
breadth = breadth[breadth['total'] > 0]

breadth['advance_ratio'] = breadth['A'] / breadth['total']

print(breadth.tail())

