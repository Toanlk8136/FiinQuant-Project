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

# 2. PARAMS
# =========================
from_date = "2026-01-28"
to_date   = "2026-01-29"

ETF_PREFIX = ('FU', 'FUC', 'E1')

tickers = [
    t for t in client.TickerList(ticker="VNINDEX")
    if not t.startswith(ETF_PREFIX)
]

print("Total tickers:", len(tickers))

# =========================
# 3. FETCH OVERVIEW (1 LẦN)
# =========================
raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

df = pd.DataFrame(raw)
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

# =========================
# 4. ADV FLAG
# =========================
df['is_adv'] = df['percentPriceChange'] > 0

# =========================
# 5. TOTAL & ADV LIQUIDITY
# =========================
liq = (
    df
    .groupby('date')
    .agg(
        total_liquidity=('totalMatchValue','sum'),
        adv_liquidity=('totalMatchValue', lambda x: x[df.loc[x.index,'is_adv']].sum())
    )
    .reset_index()
)

liq['adv_liquidity'] = liq['adv_liquidity'].fillna(0)
liq['adv_liquidity_ratio'] = liq['adv_liquidity'] / liq['total_liquidity']

# =========================
# 6. ADVANCE RATIO
# =========================
breadth = (
    df
    .groupby('date')
    .agg(
        adv_count=('is_adv','sum'),
        total_count=('ticker','count')
    )
    .reset_index()
)

breadth['advance_ratio'] = breadth['adv_count'] / breadth['total_count']

# =========================
# 7. TCI (TOP 30 CONCENTRATION)
# =========================
top30 = (
    df
    .sort_values(['date','totalMatchValue'], ascending=[True, False])
    .groupby('date')
    .head(30)
    .groupby('date')['totalMatchValue']
    .sum()
    .reset_index(name='top30_liquidity')
)

tci = liq[['date','total_liquidity']].merge(top30, on='date')
tci['TCI'] = tci['top30_liquidity'] / tci['total_liquidity']

# =========================
# 8. VNINDEX CLOSE & CHANGE
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
vn['date'] = pd.to_datetime(vn['timestamp']).dt.normalize()
vn = vn.sort_values('date')

vn['change'] = vn['close'] - vn['close'].shift(1)

# =========================
# 9. IER
# =========================
ier = vn.merge(
    liq[['date','total_liquidity']],
    on='date',
    how='left'
)

ier['IER'] = ier['change'].abs() / (ier['total_liquidity'] / 1e12)

# =========================
# 10. FINAL MERGE – ĐÚNG THỨ TỰ CỘT
# =========================
final = (
    vn[['date','close','change']]
    .merge(liq[['date','total_liquidity','adv_liquidity','adv_liquidity_ratio']], on='date', how='left')
    .merge(ier[['date','IER']], on='date', how='left')
    .merge(breadth[['date','advance_ratio']], on='date', how='left')
    .merge(tci[['date','TCI']], on='date', how='left')
)

final = final[[
    'date',
    'close',
    'change',
    'total_liquidity',
    'adv_liquidity',
    'IER',
    'advance_ratio',
    'adv_liquidity_ratio',
    'TCI'
]]

print(final)

# =========================
# 11. EXPORT
# =========================
final.to_excel("MARKET_FULL_PACK.xlsx", index=False)
print("DONE → MARKET_FULL_PACK.xlsx")