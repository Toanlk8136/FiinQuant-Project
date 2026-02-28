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

# 2. FETCH GIÁ VNINDEX
# =========================
vnindex_raw = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VNINDEX"],
    fields=["close"],
    adjusted=True,
    by="1d",
    from_date="2025-06-13",
    to_date="2026-01-14"
).get_data()

df = pd.DataFrame(vnindex_raw)

# =========================
# 3. CHUẨN HOÁ NGÀY & SORT
# =========================
df['date'] = pd.to_datetime(df['timestamp']).dt.normalize()
df = df.sort_values('date')

# =========================
# 4. TÍNH ĐIỂM TĂNG / GIẢM
# =========================
df['index_point_change'] = df['close'] - df['close'].shift(1)

# =========================
# 5. KẾT QUẢ CUỐI
# =========================
result = df[['date', 'close', 'index_point_change']]

print(result.tail(10))

result.to_excel(
    "VNIndex_daily_point_change.xlsx",
    index=False
)

print("DONE – đã xuất file VNIndex_daily_point_change.xlsx")




