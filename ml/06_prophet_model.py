"""
Bước 6a: Model Baseline — Facebook Prophet
Chạy: python ml/06_prophet_model.py
Cần cài: pip install prophet mlflow pyarrow
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")          # Chạy không cần display (trong container)
import matplotlib.pyplot as plt
from prophet import Prophet
from sklearn.metrics import mean_absolute_percentage_error
import mlflow
import mlflow.sklearn
import os

# ============================================
# Cấu hình
# ============================================
ZONE_ID    = 161
DATA_PATH  = r"D:\nyc_data\processed\demand_features_2025.parquet"
OUTPUT_DIR = r"D:\nyc_data\output\plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("nyc_demand_forecast")
# ============================================

print("=" * 60)
print("🔮 Bước 6a: Prophet Baseline Model")
print(f"   Zone: {ZONE_ID} (Midtown Center)")
print("=" * 60)

# Load & prep data
df = pd.read_parquet(DATA_PATH)
zone_df = df[df["PULocationID"] == ZONE_ID].copy()
zone_df["ds"] = (
    pd.to_datetime(zone_df["pickup_date"]) +
    pd.to_timedelta(zone_df["pickup_hour"], unit="h")
)
zone_df = zone_df.rename(columns={"demand_count": "y"})[["ds", "y"]].sort_values("ds")

print(f"\n📊 Dữ liệu zone {ZONE_ID}: {len(zone_df):,} điểm thời gian")

# Time-series split (KHÔNG dùng random shuffle!)
train = zone_df[zone_df["ds"] <  "2025-10-01"]
val   = zone_df[(zone_df["ds"] >= "2025-10-01") & (zone_df["ds"] < "2025-11-01")]
test  = zone_df[zone_df["ds"] >= "2025-11-01"]

print(f"   Train: {len(train):,}  |  Val: {len(val):,}  |  Test: {len(test):,}")

# Huấn luyện
with mlflow.start_run(run_name=f"prophet_zone{ZONE_ID}"):
    model = Prophet(
        weekly_seasonality=True,
        daily_seasonality=True,
        yearly_seasonality=False,   # Chỉ 1 năm — không đủ data
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05
    )
    model.fit(train)

    # Dự báo trên test set
    future = model.make_future_dataframe(
        periods=len(test), freq="H", include_history=False
    )
    future["ds"] = test["ds"].values
    forecast = model.predict(future)

    y_true = test["y"].values
    y_pred = forecast["yhat"].values[:len(y_true)]
    y_pred = np.maximum(y_pred, 0)   # Demand không âm

    mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mae  = np.mean(np.abs(y_true - y_pred))

    print(f"\n📈 Kết quả Prophet (Zone {ZONE_ID}):")
    print(f"   MAPE : {mape:.2f}%   {'✅ Tốt' if mape < 20 else '⚠️ > 20%'}")
    print(f"   RMSE : {rmse:.2f}")
    print(f"   MAE  : {mae:.2f}")

    # Log vào MLflow
    mlflow.log_params({
        "model":          "Prophet",
        "zone_id":        ZONE_ID,
        "weekly_seasonality": True,
        "seasonality_mode":   "multiplicative"
    })
    mlflow.log_metrics({"mape": round(mape, 4), "rmse": round(rmse, 4), "mae": round(mae, 4)})

    # Vẽ plot
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(test["ds"].values[:200], y_true[:200],  label="Actual",    alpha=0.8)
    ax.plot(test["ds"].values[:200], y_pred[:200],  label="Predicted", alpha=0.8, linestyle="--")
    ax.set_title(f"Prophet — Zone {ZONE_ID} (Test: Nov–Dec 2025)")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Demand (chuyến/giờ)")
    ax.legend()
    plt.tight_layout()
    plot_path = f"{OUTPUT_DIR}/prophet_zone{ZONE_ID}.png"
    plt.savefig(plot_path, dpi=100)
    mlflow.log_artifact(plot_path)
    print(f"\n   📊 Plot đã lưu: {plot_path}")

print("\n✅ Bước 6a hoàn tất! Xem kết quả tại http://localhost:5000")
