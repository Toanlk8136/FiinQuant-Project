from FiinQuantX import FiinSession
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# CONFIG
# =========================
username = "toanluukhanh1999@gmail.com"
password = "tua9haha"

FROM_DATE = "2024-11-01"
TO_DATE   = "2026-02-27"

JSON_KEY_FILE = "regimetree.json"  # key service account của anh
SHEET_ID = "16zDBShM2jD2aIol5qZnw1oBQqe5X7cIxqgKPFWMduQg"
WORKSHEET_NAME = "VNINDEX_OHLC"    # tab sẽ ghi (tự tạo nếu chưa có)

# =========================
# 1) LOGIN FIINQUANT
# =========================
client = FiinSession(username=username, password=password).login()
print("FiinQuant login OK:", type(client))

# =========================
# 2) FETCH VNINDEX OHLCV
# =========================
raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VNINDEX"],
    fields=["open", "high", "low", "close", "volume"],
    adjusted=True,
    by="1d",
    from_date=FROM_DATE,
    to_date=TO_DATE
).get_data()

df = pd.DataFrame(raw)
df["date"] = pd.to_datetime(df["timestamp"]).dt.normalize()
df = df.sort_values("date")

# Chuẩn hoá cột output
df_out = df[["date", "ticker", "open", "high", "low", "close", "volume"]].copy()
df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")

print("Rows:", len(df_out))
print(df_out.head())

# =========================
# 3) CONNECT GOOGLE SHEETS
# =========================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_FILE, scope)
client_gs = gspread.authorize(creds)
spreadsheet = client_gs.open_by_key(SHEET_ID)

# get or create worksheet
try:
    ws = spreadsheet.worksheet(WORKSHEET_NAME)
except gspread.WorksheetNotFound:
    ws = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=str(max(2000, len(df_out)+50)), cols="10")

# =========================
# 4) PUSH TO SHEET
# =========================
ws.clear()
set_with_dataframe(ws, df_out, row=1, col=1, include_column_header=True)

print(f"DONE -> pushed to Google Sheet tab '{WORKSHEET_NAME}'")