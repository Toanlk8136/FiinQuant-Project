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

# CONFIG
# =========================
ROLL = 60
from_date = "2024-11-01"
to_date   = "2026-02-13"

ETF_PREFIX = ('FU', 'FUC', 'E1')

# =========================
# HELPER: rolling percentile rank
# =========================
def rolling_pr(series, window, min_periods=20):
    series = pd.to_numeric(series, errors="coerce")
    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1],
        raw=False
    )

# =========================
# TICKERS
# =========================
tickers = client.TickerList(ticker="VNINDEX")
tickers = [t for t in tickers if not t.startswith(ETF_PREFIX)]
print("Total tickers:", len(tickers))

TECHNO = [
    "CTR","VTP","FPT","HPG","ACB","MBB","MWG","MSN",
    "SSI","VPB","VNM","SHB","VIB","SAB","GMD","VHC"
]

CONTROL = [
    "VIC","VHM","VRE","GEX","EIB","VIX","GAS","PLX","PVD",
    "VSC","HDB","VJC","VCB","BID","GVR","BCM","POW","LPB","TCB"
]

# =========================
# 1) OVERVIEW – ALL MARKET (1 lần)
# =========================
raw = client.PriceStatistics().get_overview(
    tickers=tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

df = pd.DataFrame(raw)
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()

# ĐƠN VỊ → TỶ
df['totalMatchValue'] = pd.to_numeric(df['totalMatchValue'], errors='coerce') / 1e9
df['marketCap']       = pd.to_numeric(df['marketCap'], errors='coerce') / 1e9
df['percentPriceChange'] = pd.to_numeric(df['percentPriceChange'], errors='coerce')

df = df.dropna(subset=['date','ticker','totalMatchValue','marketCap'])

df['is_adv'] = df['percentPriceChange'] > 0

# =========================
# 2) LIQUIDITY + MARKET CAP + BREADTH
# =========================
liq = (
    df.groupby('date')
      .agg(
          total_liquidity=('totalMatchValue','sum'),
          total_market_cap=('marketCap','sum'),
          adv_liquidity=('totalMatchValue', lambda x: x[df.loc[x.index,'is_adv']].sum())
      )
      .reset_index()
)

liq['adv_liquidity'] = liq['adv_liquidity'].fillna(0)
liq['adv_liquidity_ratio'] = liq['adv_liquidity'] / liq['total_liquidity']

breadth = (
    df.groupby('date')
      .agg(
          adv_count=('is_adv','sum'),
          total_count=('ticker','count')
      )
      .reset_index()
)
breadth['advance_ratio'] = breadth['adv_count'] / breadth['total_count']

# =========================
# 3) TECHNO vs CONTROL (liq/mcap + pct_change group)
#    pct_change_group: mcap-weighted %change (để dùng B4)
# =========================
df['group'] = np.where(
    df['ticker'].isin(TECHNO), 'TECHNO',
    np.where(df['ticker'].isin(CONTROL), 'CONTROL', 'OTHER')
)

gdf = df[df['group'].isin(['TECHNO','CONTROL'])].copy()

group_daily = (
    gdf.groupby(['date','group'])
       .agg(
           liq=('totalMatchValue','sum'),
           mcap=('marketCap','sum'),
           # mcap-weighted percent change:
           pct_change=('percentPriceChange',
                       lambda x: np.average(
                           x.fillna(0).to_numpy(),
                           weights=gdf.loc[x.index,'marketCap'].fillna(0).to_numpy()
                       ) if gdf.loc[x.index,'marketCap'].fillna(0).sum() > 0 else np.nan)
       )
       .reset_index()
)

panel = group_daily.pivot(index='date', columns='group', values=['liq','mcap','pct_change'])
panel.columns = [
    'liq_control','liq_techno',
    'mcap_control','mcap_techno',
    'pct_change_control','pct_change_techno'
]
panel = panel.reset_index()

# =========================
# 4) VNINDEX PRICE (close + change)
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
# 5) VN30 REAL LIQUIDITY + VN30 MARKET CAP (cho OT)
# =========================
vn30_tickers = client.TickerList(ticker="VN30")

vn30_raw = client.PriceStatistics().get_overview(
    tickers=vn30_tickers,
    time_filter="Daily",
    from_date=from_date,
    to_date=to_date
)

vn30_df = pd.DataFrame(vn30_raw)
vn30_df['date'] = pd.to_datetime(vn30_df['timestamp']).dt.normalize()
vn30_df['totalMatchValue'] = pd.to_numeric(vn30_df['totalMatchValue'], errors='coerce') / 1e9
vn30_df['marketCap']       = pd.to_numeric(vn30_df['marketCap'], errors='coerce') / 1e9
vn30_df = vn30_df.dropna(subset=['date','totalMatchValue','marketCap'])

vn30_daily = (
    vn30_df.groupby('date')
           .agg(
               liq_vn30=('totalMatchValue','sum'),
               mcap_vn30=('marketCap','sum')
           )
           .reset_index()
)

# =========================
# 6) MERGE CORE FEATURES
# =========================
data = (
    vn[['date','close','change']]
    .merge(liq, on='date', how='left')
    .merge(breadth[['date','advance_ratio']], on='date', how='left')
    .merge(panel, on='date', how='left')
    .merge(vn30_daily, on='date', how='left')
)

# =========================
# 7) IER – điểm / 1.000 tỷ (same style anh)
# =========================
data['IER'] = data['change'].abs() / (data['total_liquidity'] / 1000)

# =========================
# 8) VN30 ratios + IER_vn30
# =========================
data['vn30_liq_ratio']  = data['liq_vn30']  / data['total_liquidity']
data['vn30_mcap_ratio'] = data['mcap_vn30'] / data['total_market_cap']
data['IER_vn30'] = data['change'].abs() / (data['liq_vn30'] / 1000)

# =========================
# 9) TO & OT (TREE v2)
#    TO = total_liquidity / total_market_cap
#    OT = (vn30_liq_ratio) / (vn30_mcap_ratio)
# =========================
data['TO'] = data['total_liquidity'] / data['total_market_cap']
data['OT'] = data['vn30_liq_ratio'] / data['vn30_mcap_ratio']

# =========================
# 10) PERCENTILE FEATURES (PR60)
#     (TREE v2 uses PR_change, PR_ADV, PR_LAR, PR_total_liquidity, PR_IER, PR_TO, PR_OT)
# =========================
PR_COLS = [
    'change', 'IER', 'total_liquidity', 'advance_ratio', 'adv_liquidity_ratio',
    'TO', 'OT',
    # B4:
    'liq_techno','liq_control','mcap_techno','mcap_control'
]

for c in PR_COLS:
    data[f'PR_{c}'] = rolling_pr(data[c], ROLL, min_periods=20)

# =========================
# 11) REGIME TREE v2 (TO/OT, no TCI)  — y như file rules
# =========================
def regime_row_v2(r):
    # B1 action
    if r['PR_change'] <= 0.10:
        action = 'PULL'
    elif r['PR_change'] >= 0.90:
        action = 'PUSH'
    else:
        return 'SKIP | NONE | NONE | NONE'

    # B2 structure (uses PR_OT)
    if action == 'PUSH':
        if (r['PR_advance_ratio'] >= 0.70) and (r['PR_adv_liquidity_ratio'] >= 0.70):
            structure = 'BROAD_MARK_UP'
        elif (r['PR_OT'] >= 0.70) and (r['PR_advance_ratio'] <= 0.50):
            structure = 'PILLAR_PULL_UP'
        else:
            structure = 'TECHNICAL_BOUNCE'
    else:  # PULL
        if (r['PR_advance_ratio'] <= 0.30) and (r['PR_adv_liquidity_ratio'] <= 0.30):
            structure = 'BROAD_MARK_DOWN'
        elif (r['PR_OT'] >= 0.70) and (r['PR_advance_ratio'] >= 0.40):
            structure = 'PILLAR_PUSH_DOWN'
        else:
            structure = 'TECHNICAL_DIP'

    # B3 flow quality (uses PR_TO + PR_total_liquidity + PR_IER)
    # heat tag
    if (r['PR_TO'] >= 0.70) and (r['PR_total_liquidity'] >= 0.70):
        heat = 'HIGH_HEAT'
    elif (r['PR_TO'] <= 0.30) and (r['PR_total_liquidity'] <= 0.30):
        heat = 'LOW_HEAT'
    else:
        heat = 'MID_HEAT'

    # efficiency tag
    if r['PR_IER'] >= 0.70:
        eff = 'HIGH_EFF'
    elif r['PR_IER'] <= 0.30:
        eff = 'LOW_EFF'
    else:
        eff = 'MID_EFF'

    if (heat == 'HIGH_HEAT') and (eff == 'HIGH_EFF'):
        flow_q = 'GOOD'
    elif (heat == 'LOW_HEAT') and (eff == 'LOW_EFF'):
        flow_q = 'BAD'
    else:
        flow_q = 'MEDIUM'

    # B4 bucket (requires pct_change_techno/control + PR mcap/liq)
    bucket = 'MIXED_OR_ROTATION'
    if (r['PR_mcap_techno'] >= 0.70) and (r['PR_liq_techno'] >= 0.60) and (r['pct_change_techno'] > r['pct_change_control']):
        bucket = 'TECHNO'
    elif (r['PR_mcap_control'] >= 0.70) and (r['PR_liq_control'] >= 0.60) and (r['pct_change_control'] > r['pct_change_techno']):
        bucket = 'CONTROL'

    return f"{action} | {structure} | {flow_q} | {bucket}"

data['REGIME'] = data.apply(regime_row_v2, axis=1)

# =========================
# 12) FLAGS (append-only, theo rules file)
# =========================
data['deleveraging_flag'] = (
    (data['PR_TO'] >= 0.80) &
    (data['PR_advance_ratio'] <= 0.30) &
    (data['PR_adv_liquidity_ratio'] <= 0.30)
).astype(int)

data['core_absorption_flag'] = (data['PR_OT'] >= 0.70).astype(int)

data['engineering_flag'] = (
    (data['PR_OT'] >= 0.70) &
    (data['PR_TO'] <= 0.40)
).astype(int)

# (Optional) keep tags for debug
def heat_tag_row(r):
    if (r['PR_TO'] >= 0.70) and (r['PR_total_liquidity'] >= 0.70):
        return 'HIGH_HEAT'
    if (r['PR_TO'] <= 0.30) and (r['PR_total_liquidity'] <= 0.30):
        return 'LOW_HEAT'
    return 'MID_HEAT'

def eff_tag_row(r):
    if r['PR_IER'] >= 0.70:
        return 'HIGH_EFF'
    if r['PR_IER'] <= 0.30:
        return 'LOW_EFF'
    return 'MID_EFF'

data['HEAT_TAG'] = data.apply(heat_tag_row, axis=1)
data['EFF_TAG']  = data.apply(eff_tag_row, axis=1)

# =========================
# 13) VN30 TAG – giữ nguyên style anh (dùng PR_vn30_liq_ratio & PR_IER_vn30)
# =========================
# PR cho vn30_liq_ratio & IER_vn30
data['PR_vn30_liq_ratio'] = rolling_pr(data['vn30_liq_ratio'], ROLL, min_periods=20)
data['PR_IER_vn30'] = rolling_pr(data['IER_vn30'], ROLL, min_periods=20)

def vn30_tag(r):
    if r['PR_vn30_liq_ratio'] >= 0.70:
        mode = 'HEAVY_VN30'
    elif r['PR_vn30_liq_ratio'] <= 0.30:
        mode = 'NO_VN30'
    else:
        mode = 'NORMAL_VN30'

    if r['PR_IER_vn30'] >= 0.70:
        eff = 'STRONG_TRU'
    elif r['PR_IER_vn30'] <= 0.30:
        eff = 'WEAK_TRU'
    else:
        eff = 'NORMAL_TRU'

    role = 'PASSIVE'
    if ('PILLAR' in str(r['REGIME'])) and (mode == 'HEAVY_VN30') and (eff == 'WEAK_TRU'):
        role = 'BAIT'
    elif mode == 'HEAVY_VN30':
        role = 'DRIVER'

    return f"{mode} | {eff} | {role}"

data['VN30_TAG'] = data.apply(vn30_tag, axis=1)

# =========================
# 14) EXPORT EXCEL
# =========================
with pd.ExcelWriter("REGIME_OUTPUT_v2_TO_OT_no_TCI.xlsx") as writer:
    data.to_excel(writer, sheet_name="DATA", index=False)
    data[['date','REGIME','VN30_TAG','deleveraging_flag','core_absorption_flag','engineering_flag']].to_excel(
        writer, sheet_name="OUTPUT", index=False
    )

print("DONE – REGIME_OUTPUT_v2_TO_OT_no_TCI.xlsx")