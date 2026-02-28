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

# 2. KHAI BÁO NHÓM
# =========================
TECHNO = [
    "CTR","VTP","FPT","HPG","ACB","MBB","MWG","MSN",
    "SSI","VPB","VNM","SHB","VIB","SAB","GMD","VHC"
]

CONTROL = [
    "VIC","VHM","VRE",
    "GEX","EIB","VIX",
    "GAS","PLX","PVD",
    "VSC","HDB","VJC",
    "VCB","BID",
    "GVR","BCM","POW","LPB","TCB"
]

ALL_TICKERS = list(set(TECHNO + CONTROL))

# =========================
# 3. TIME RANGE
# =========================
from_date = "2026-01-28"
to_date   = "2026-01-29"

# =========================
# 4. FETCH OVERVIEW (LIQ + MCAP)
# =========================
raw = client.PriceStatistics().get_overview(
    tickers=ALL_TICKERS,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

df = pd.DataFrame(raw)
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

# Gán group
df['group'] = df['ticker'].apply(
    lambda x: 'TECHNO' if x in TECHNO else 'CONTROL'
)

# =========================
# 5. AGG THEO NGÀY – THEO NHÓM
# =========================
daily = (
    df
    .groupby(['date','group'])
    .agg(
        liquidity=('totalMatchValue','sum'),
        market_cap=('marketCap','sum')
    )
    .reset_index()
)

panel = daily.pivot(
    index='date',
    columns='group',
    values=['liquidity','market_cap']
)

panel.columns = [
    'liq_control','liq_techno',
    'mcap_control','mcap_techno'
]

panel = panel.reset_index().sort_values('date')

# =========================
# 6. SCALE ĐƠN VỊ → NGHÌN TỶ
# =========================
for col in [
    'liq_control','liq_techno',
    'mcap_control','mcap_techno'
]:
    panel[col] = panel[col] / 1e12

# =========================
# 7. FETCH VNINDEX
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

vn['index_change'] = vn['close'] - vn['close'].shift(1)
vn = vn[['date','close','index_change']]

# =========================
# 8. MERGE VNINDEX
# =========================
panel = panel.merge(vn, on='date', how='left')

# =========================
# 9. TÍNH CÁC CHỈ BÁO
# =========================
panel['mcap_change_techno'] = panel['mcap_techno'] / panel['mcap_techno'].shift(1) - 1
panel['mcap_change_control'] = panel['mcap_control'] / panel['mcap_control'].shift(1) - 1

panel['mcap_control_to_techno'] = panel['mcap_control'] / panel['mcap_techno']
panel['liq_techno_ratio'] = panel['liq_techno'] / (panel['liq_techno'] + panel['liq_control'])

# =========================
# 10. SẮP XẾP ĐÚNG THỨ TỰ CỘT
# =========================
panel = panel[
    [
        'date',
        'close',
        'index_change',
        'liq_control',
        'mcap_control',
        'liq_techno',
        'mcap_techno',
        'mcap_change_techno',
        'mcap_change_control',
        'mcap_control_to_techno',
        'liq_techno_ratio'
    ]
]

print(panel)

# =========================
# 11. EXPORT EXCEL
# =========================
panel.to_excel(
    "TECHNO_CONTROL_DAILY_PANEL_NGHIN_TY.xlsx",
    index=False
)

print("DONE – đã xuất TECHNO_CONTROL_DAILY_PANEL_NGHIN_TY.xlsx")