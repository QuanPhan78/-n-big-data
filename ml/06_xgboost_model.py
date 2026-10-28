"""
Bước 6b: XGBoost Model (Main — thường tốt hơn Prophet với 1 năm data)
Chạy: python ml/06_xgboost_model.py
Cần cài: pip install xgboost mlflow pyarrow scikit-learn shap
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.metrics import mean_absolute_percentage_error
import mlflow
import mlflow.xgboost

# ============================================
ZONE_ID    = 161
DATA_PATH  = r"D:\nyc_data\processed\demand_features_2025.parquet"
OUTPUT_DIR = r"D:\nyc_data\output\plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
mlflow.set_tracking_uri(tracking_uri)
mlflow.set_experiment("nyc_demand_forecast")
# ============================================

print("=" * 60)
print("🤖 Bước 6b: XGBoost Demand Forecasting")
print(f"   Zone: {ZONE_ID}")
print("=" * 60)

# ---- Load ----
df = pd.read_parquet(DATA_PATH)
z  = df[df["PULocationID"] == ZONE_ID].copy()
z  = z.sort_values(["pickup_date", "pickup_hour"]).reset_index(drop=True)

# ---- Lag features ----
print("\n⚙️  Tạo lag features...")
for lag in [1, 2, 3, 6, 12, 24, 48, 168]:
    z[f"lag_{lag}h"] = z["demand_count"].shift(lag)

z["roll_mean_24h"]  = z["demand_count"].rolling(24, min_periods=1).mean()
z["roll_mean_168h"] = z["demand_count"].rolling(168, min_periods=1).mean()
z["roll_std_24h"]   = z["demand_count"].rolling(24, min_periods=1).std().fillna(0)

z.dropna(inplace=True)
print(f"   Sau dropna: {len(z):,} dòng")

FEATURES = (
    [c for c in z.columns if c.startswith("lag_") or c.startswith("roll_")] +
    ["pickup_hour", "pickup_dow", "pickup_month",
     "is_weekend", "is_rush_hour", "is_holiday"]
)

# ---- Time-series split ----
if z["pickup_date"].max() >= "2025-11-01":
    train_mask = z["pickup_date"].astype(str) <  "2025-10-01"
    val_mask   = (z["pickup_date"].astype(str) >= "2025-10-01") & (z["pickup_date"].astype(str) < "2025-11-01")
    test_mask  = z["pickup_date"].astype(str) >= "2025-11-01"
else:
    n_total = len(z)
    n_train = int(n_total * 0.70)
    n_val   = int(n_total * 0.15)
    train_mask = np.zeros(n_total, dtype=bool)
    train_mask[:n_train] = True
    val_mask = np.zeros(n_total, dtype=bool)
    val_mask[n_train:n_train + n_val] = True
    test_mask = np.zeros(n_total, dtype=bool)
    test_mask[n_train + n_val:] = True

X_train, y_train = z[train_mask][FEATURES], z[train_mask]["demand_count"]
X_val,   y_val   = z[val_mask][FEATURES],   z[val_mask]["demand_count"]
X_test,  y_test  = z[test_mask][FEATURES],  z[test_mask]["demand_count"]

print(f"\n📋 Split:")
print(f"   Train: {len(X_train):,}  |  Val: {len(X_val):,}  |  Test: {len(X_test):,}")

# ---- Train ----
with mlflow.start_run(run_name=f"xgboost_zone{ZONE_ID}"):
    params = {
        "n_estimators":  400,
        "learning_rate": 0.05,
        "max_depth":     5,
        "min_child_weight": 3,
        "subsample":     0.8,
        "colsample_bytree": 0.8,
        "reg_lambda":    1.0,
        "random_state":  42,
        "n_jobs":        -1,
        "eval_metric":   "rmse",
        "early_stopping_rounds": 30,
    }

    model = xgb.XGBRegressor(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=50
    )

    y_pred = np.maximum(model.predict(X_test), 0)

    mape = mean_absolute_percentage_error(y_test, y_pred) * 100
    rmse = np.sqrt(np.mean((y_test.values - y_pred) ** 2))
    mae  = np.mean(np.abs(y_test.values - y_pred))

    print(f"\n📈 Kết quả XGBoost (Zone {ZONE_ID}):")
    print(f"   MAPE : {mape:.2f}%   {'✅ Tốt' if mape < 20 else '⚠️ > 20%'}")
    print(f"   RMSE : {rmse:.2f}")
    print(f"   MAE  : {mae:.2f}")

    # Log
    mlflow.log_params({"model": "XGBoost", "zone_id": ZONE_ID, **params})
    mlflow.log_metrics({"mape": round(mape,4), "rmse": round(rmse,4), "mae": round(mae,4)})
    mlflow.xgboost.log_model(model, "xgboost_model",
                              registered_model_name="nyc_demand_xgboost")

    # Feature Importance
    fi = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    fi.head(15).plot(kind="barh", ax=ax)
    ax.set_title("XGBoost — Top 15 Feature Importance")
    ax.invert_yaxis()
    plt.tight_layout()
    fi_path = f"{OUTPUT_DIR}/xgboost_feature_importance.png"
    plt.savefig(fi_path, dpi=100)
    mlflow.log_artifact(fi_path)

    # Actual vs Predicted
    fig2, ax2 = plt.subplots(figsize=(14, 5))
    n = min(300, len(y_test))
    ax2.plot(range(n), y_test.values[:n],  label="Actual",    alpha=0.85)
    ax2.plot(range(n), y_pred[:n],         label="Predicted", alpha=0.85, linestyle="--")
    ax2.set_title(f"XGBoost — Zone {ZONE_ID} | MAPE={mape:.1f}%")
    ax2.set_xlabel("Giờ")
    ax2.set_ylabel("Demand")
    ax2.legend()
    plt.tight_layout()
    pred_path = f"{OUTPUT_DIR}/xgboost_predictions_zone{ZONE_ID}.png"
    plt.savefig(pred_path, dpi=100)
    mlflow.log_artifact(pred_path)

    print(f"\n   📊 Plots: {fi_path}")
    print(f"   📊        {pred_path}")

print("\n✅ Bước 6b hoàn tất! Model đã đăng ký tại MLflow registry.")
print("   Xem kết quả: http://localhost:5000")
