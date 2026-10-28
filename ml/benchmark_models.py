"""
ml/benchmark_models.py — So sánh thực nghiệm hiệu năng các mô hình dự báo nhu cầu:
1. Linear Regression (Baseline 1)
2. Random Forest Regressor (Baseline 2)
3. XGBoost Regressor (Đề xuất)
"""
import sys
import os
import time
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import xgboost as xgb

ZONE_ID = 161  # Midtown Center
DATA_PATH = r"D:\nyc_data\processed\demand_features_2025.parquet"
OUTPUT_DIR = r"D:\nyc_data\output\models"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print(f"📊 BENCHMARK SO SÁNH CÁC MÔ HÌNH HỌC MÁY — ZONE {ZONE_ID} (Midtown Center)")
print("=" * 70)

df = pd.read_parquet(DATA_PATH)
z = df[df["PULocationID"] == ZONE_ID].copy()
z = z.sort_values(["pickup_date", "pickup_hour"]).reset_index(drop=True)

# Tạo lag & rolling features
for lag in [1, 2, 3, 6, 12, 24, 48, 168]:
    z[f"lag_{lag}h"] = z["demand_count"].shift(lag)

z["roll_mean_24h"] = z["demand_count"].rolling(24, min_periods=1).mean()
z["roll_mean_168h"] = z["demand_count"].rolling(168, min_periods=1).mean()
z["roll_std_24h"] = z["demand_count"].rolling(24, min_periods=1).std().fillna(0)

z.dropna(inplace=True)
print(f"✅ Dữ liệu sau khi tạo đặc trưng trễ: {len(z):,} dòng")

FEATURES = (
    [c for c in z.columns if c.startswith("lag_") or c.startswith("roll_")] +
    ["pickup_hour", "pickup_dow", "pickup_month",
     "is_weekend", "is_rush_hour", "is_holiday"]
)

n_total = len(z)
n_train = int(n_total * 0.80)

X_train, y_train = z.iloc[:n_train][FEATURES], z.iloc[:n_train]["demand_count"]
X_test, y_test = z.iloc[n_train:][FEATURES], z.iloc[n_train:]["demand_count"]

print(f"📋 Tập huấn luyện (Train): {len(X_train):,} dòng | Tập kiểm thử (Test): {len(X_test):,} dòng")
print("-" * 70)

models = {
    "Linear Regression (Baseline 1)": LinearRegression(),
    "Random Forest (Baseline 2)": RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1),
    "XGBoost Regressor (Đề xuất)": xgb.XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
}

results = []

for name, model in models.items():
    print(f"🔄 Đang huấn luyện mô hình: {name}...")
    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    train_time = time.perf_counter() - t0
    
    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0)  # Nhu cầu không âm
    
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    results.append({
        "Model": name,
        "RMSE": round(float(rmse), 2),
        "MAE": round(float(mae), 2),
        "R2_Score": round(float(r2), 4),
        "Train_Time_Sec": round(float(train_time), 2)
    })
    print(f"   -> Hoàn thành trong {train_time:.2f}s | RMSE={rmse:.2f} | MAE={mae:.2f} | R²={r2:.4f}")

# Lưu kết quả
res_df = pd.DataFrame(results)
csv_out = os.path.join(OUTPUT_DIR, "model_benchmark_comparison.csv")
json_out = os.path.join(OUTPUT_DIR, "model_benchmark_comparison.json")

res_df.to_csv(csv_out, index=False, encoding="utf-8")
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("🏆 KẾT QUẢ SO SÁNH THỰC NGHIỆM ĐA MÔ HÌNH (BENCHMARK RESULTS)")
print("=" * 70)
print(res_df.to_string(index=False))
print(f"\n💾 Đã lưu kết quả tại:\n  - {csv_out}\n  - {json_out}")
