import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===== CONFIG =====
SERVICE_ACCOUNT_JSON = r"regimetree.json"
SPREADSHEET_ID = "16zDBShM2jD2aIol5qZnw1oBQqe5X7cIxqgKPFWMduQg"
TAB_NAME = "VNINDEX_OHLC"

# ===== 1) Connect Google Sheets =====
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_JSON, scope)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.worksheet(TAB_NAME)

# ===== 2) Read -> DataFrame =====
rows = ws.get_all_records()
df = pd.DataFrame(rows)
if df.empty:
    raise ValueError("Sheet VNINDEX_OHLC is empty.")

df.columns = [c.strip() for c in df.columns]
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

def to_num(x):
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    return pd.to_numeric(s, errors="coerce")

for c in ["open", "high", "low", "close"]:
    df[c] = df[c].apply(to_num)

if "volume" in df.columns:
    df["volume"] = df["volume"].apply(to_num)
else:
    df["volume"] = pd.NA

df = df.dropna(subset=["open", "high", "low", "close"]).copy()
df["date"] = df["date"].dt.normalize()

# ===== 3) Build missing WEEKDAYS (holidays) list =====
# expected weekdays (Mon-Fri) between min/max
expected_weekdays = pd.date_range(df["date"].min(), df["date"].max(), freq="B")  # business day
have_days = pd.DatetimeIndex(df["date"].unique())
missing_weekdays = expected_weekdays.difference(have_days)

# Plotly rangebreak values: safest pass as 'YYYY-MM-DD' strings
missing_values = [d.strftime("%Y-%m-%d") for d in missing_weekdays]

print("Rows:", len(df))
print("Missing weekdays (holiday-like gaps):", len(missing_values))

# ===== 4) Plot: candlestick + volume =====
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.02,
    row_heights=[0.75, 0.25]
)

fig.add_trace(
    go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="VNINDEX",
        increasing_line_color="#00a86b",
        decreasing_line_color="#e53935",
        increasing_fillcolor="#00a86b",
        decreasing_fillcolor="#e53935",
    ),
    row=1, col=1
)

vol_colors = ["#00a86b" if c >= o else "#e53935" for o, c in zip(df["open"], df["close"])]

fig.add_trace(
    go.Bar(
        x=df["date"],
        y=df["volume"],
        marker_color=vol_colors,
        opacity=0.6,
        name="Volume"
    ),
    row=2, col=1
)

# ===== 5) IMPORTANT: rangebreaks apply to BOTH x-axes =====
rb = [
    dict(bounds=["sat", "mon"]),   # skip weekends
    dict(values=missing_values),   # skip missing weekdays (holidays / gaps)
]

# apply to row1 and row2 explicitly
fig.update_xaxes(rangebreaks=rb, row=1, col=1)
fig.update_xaxes(rangebreaks=rb, row=2, col=1)

# Add quick range buttons (optional)
fig.update_xaxes(
    rangeselector=dict(
        buttons=list([
            dict(count=1, label="1m", step="month", stepmode="backward"),
            dict(count=3, label="3m", step="month", stepmode="backward"),
            dict(count=6, label="6m", step="month", stepmode="backward"),
            dict(count=1, label="YTD", step="year", stepmode="todate"),
            dict(count=1, label="1y", step="year", stepmode="backward"),
            dict(step="all", label="All"),
        ])
    ),
    row=1, col=1
)

fig.update_layout(
    title="VNINDEX Candlestick + Volume (skip weekends + holidays)",
    height=850,
    showlegend=False,
    xaxis_rangeslider_visible=False,  # volume đã là panel dưới
)

fig.update_yaxes(title_text="Index", row=1, col=1)
fig.update_yaxes(title_text="Volume", row=2, col=1)

fig.show()