from pathlib import Path
import json
import pandas as pd
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== CONFIG ======
SERVICE_ACCOUNT_JSON = r"regimetree.json"
SPREADSHEET_ID = "16zDBShM2jD2aIol5qZnw1oBQqe5X7cIxqgKPFWMduQg"
SHEET_GID = 478891540          # optional fallback
TAB_NAME = "VNINDEX_OHLC"

OUTPUT_DIR = Path(r"C:/Users/Admin/PycharmProjects/FiinQuant Project/frontend")
GLOBAL_VAR_NAME = "VNSTOCK_DATA"  # window.VNSTOCK_DATA = ...

JSON_OUT = OUTPUT_DIR / "vnindex_ohlc.json"
JS_OUT   = OUTPUT_DIR / "vnindex_ohlc.js"

# ====== HELPERS ======
def to_num(x):
    """Parse numbers robustly, handles commas and blanks."""
    if x is None:
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return np.nan
    s = s.replace(",", "")  # "126,239" -> "126239"
    return pd.to_numeric(s, errors="coerce")

def median_safe(arr):
    arr = pd.Series(arr).dropna()
    if arr.empty:
        return np.nan
    return float(arr.median())

def auto_scale_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fix common sheet/export issues:
    - close/high/low in 1.x (should be ~1xxx) => multiply by 1000
    - open in 100k (e.g. 126239 meaning 1262.39*100) => divide by 10/100/1000 to match close
    """
    out = df.copy()

    med_close = median_safe(out["close"])
    med_open  = median_safe(out["open"])

    # Case A: close around 1.x or 10.x -> likely missing *1000
    # VNINDEX should be ~1000-2000 historically; use conservative heuristic
    if np.isfinite(med_close) and med_close < 50:
        for c in ["open", "high", "low", "close"]:
            out[c] = out[c] * 1000.0

    # Recompute medians after possible multiply
    med_close = median_safe(out["close"])
    med_open  = median_safe(out["open"])

    # Case B: open hugely larger than close (e.g. open is 126239 vs close 1254)
    # Adjust open per-row by choosing divisor that makes open closest to close.
    divisors = [1.0, 10.0, 100.0, 1000.0, 10000.0]
    if np.isfinite(med_open) and np.isfinite(med_close) and med_open > 10 * med_close:
        # choose best divisor globally using medians
        best_d = 1.0
        best_err = float("inf")
        for d in divisors:
            err = abs((med_open / d) - med_close)
            if err < best_err:
                best_err = err
                best_d = d
        out["open"] = out["open"] / best_d

    # Per-row fine-tune open if still off vs close (optional but helpful)
    # Choose divisor for each row (keeps stable even if some rows differ)
    o = out["open"].to_numpy()
    c = out["close"].to_numpy()
    o_new = o.copy()

    for i in range(len(out)):
        if not (np.isfinite(o[i]) and np.isfinite(c[i])):
            continue
        best = o[i]
        best_err = abs(best - c[i])
        for d in divisors:
            cand = o[i] / d
            err = abs(cand - c[i])
            if err < best_err:
                best_err = err
                best = cand
        o_new[i] = best

    out["open"] = o_new

    # Ensure high/low envelopes open/close
    out["high"] = np.maximum.reduce([out["high"].to_numpy(), out["open"].to_numpy(), out["close"].to_numpy()])
    out["low"]  = np.minimum.reduce([out["low"].to_numpy(),  out["open"].to_numpy(), out["close"].to_numpy()])

    return out

# ====== 1) CONNECT GOOGLE SHEETS ======
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_JSON, scope)
gc = gspread.authorize(creds)
sh = gc.open_by_key(SPREADSHEET_ID)

# Prefer by tab name; fallback by gid
try:
    ws = sh.worksheet(TAB_NAME)
except Exception:
    ws = sh.get_worksheet_by_id(SHEET_GID)

print("Reading worksheet:", ws.title)

# ====== 2) READ -> DATAFRAME ======
rows = ws.get_all_records()
df = pd.DataFrame(rows)

if df.empty:
    raise ValueError("Worksheet is empty. Nothing to export.")

df.columns = [c.strip() for c in df.columns]

# Required columns
required = ["date", "open", "high", "low", "close"]
missing = [c for c in required if c not in df.columns]
if missing:
    raise ValueError(f"Missing columns {missing}. Current columns: {df.columns.tolist()}")

# Parse date
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.dropna(subset=["date"]).copy()
df["date"] = df["date"].dt.normalize()

# Parse numbers
for c in ["open", "high", "low", "close"]:
    df[c] = df[c].apply(to_num)

if "volume" in df.columns:
    df["volume"] = df["volume"].apply(to_num)
else:
    df["volume"] = np.nan

# Drop invalid OHLC rows
df = df.dropna(subset=["open", "high", "low", "close"]).copy()
df = df.sort_values("date").reset_index(drop=True)

# ====== 3) AUTO-FIX SCALE (CRITICAL) ======
before_med = {
    "open": float(pd.Series(df["open"]).median()),
    "close": float(pd.Series(df["close"]).median()),
}
df = auto_scale_prices(df)
after_med = {
    "open": float(pd.Series(df["open"]).median()),
    "close": float(pd.Series(df["close"]).median()),
}

# ====== 4) BUILD PAYLOAD ======
# Plotly likes ISO date strings; also ok for JS chart libs
df_out = df[["date", "open", "high", "low", "close", "volume"]].copy()
df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")

records = df_out.to_dict(orient="records")

payload = {
    "meta": {
        "source": "GoogleSheet",
        "spreadsheet_id": SPREADSHEET_ID,
        "worksheet": ws.title,
        "rows": len(records),
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "median_before": before_med,
        "median_after": after_med,
        "notes": "OHLC normalized for financial candlestick plotting (commas parsed, scale fixed, high/low enforced)."
    },
    "data": records
}

# ====== 5) WRITE JSON + JS ======
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(JSON_OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False)

with open(JS_OUT, "w", encoding="utf-8") as f:
    f.write(f"window.{GLOBAL_VAR_NAME} = ")
    json.dump(payload, f, ensure_ascii=False)
    f.write(";")

print("✅ Exported:")
print(" -", JSON_OUT)
print(" -", JS_OUT)
print("Rows:", len(records))
print("Median (before):", before_med, "-> (after):", after_med)