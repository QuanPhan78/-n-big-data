"""
execute_business_analytics.py — Phân tích Nghiệp Vụ Chuyên Sâu:
1. Doanh thu & Tiền tip (Revenue & Tip Analytics)
2. Cung đường vàng Origin-Destination (O-D Corridors) & Luồng di chuyển liên quận
3. Huấn luyện mô hình XGBoost cho Top 5 Zones bận rộn nhất New York
"""
import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import xgboost as xgb
from sklearn.metrics import mean_absolute_percentage_error
import mlflow
import mlflow.xgboost

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = r"D:\nyc_data"
REPO_DIR = os.path.abspath("./data")
PARQUET_FILE = os.path.join(DATA_DIR, "yellow", "yellow_tripdata_2025-01.parquet")
ZONE_FILE = os.path.join(DATA_DIR, "zone", "taxi_zone_lookup.csv")

OUT_SQL_DIR = os.path.join(DATA_DIR, "output", "sql_results")
PLOTS_DIR = os.path.join(DATA_DIR, "output", "plots")
MODELS_DIR = os.path.join(DATA_DIR, "output", "models")

for d in [OUT_SQL_DIR, PLOTS_DIR, MODELS_DIR]:
    os.makedirs(d, exist_ok=True)

# Cấu hình MLflow
mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
mlflow.set_experiment("nyc_demand_forecast")

PAYMENT_MAP = {
    1: "Thẻ tín dụng (Credit Card)",
    2: "Tiền mặt (Cash)",
    3: "Miễn phí (No Charge)",
    4: "Tranh chấp (Dispute)",
    5: "Không rõ (Unknown)"
}

TOP_ZONES = [
    (237, "Upper East Side South"),
    (161, "Midtown Center"),
    (132, "JFK Airport"),
    (236, "Upper East Side North"),
    (186, "Penn Station / Madison Sq")
]

def load_data():
    print("=" * 60)
    print("1. TẢI DỮ LIỆU ĐỂ PHÂN TÍCH NGHIỆP VỤ")
    print("=" * 60)
    df = pd.read_parquet(PARQUET_FILE)
    zones = pd.read_csv(ZONE_FILE)
    print(f"  Loaded raw trips: {len(df):,} rows")
    print(f"  Loaded taxi zones: {len(zones):,} zones")

    # Lọc chuyến hợp lệ
    df['duration_min'] = (pd.to_datetime(df['tpep_dropoff_datetime']) - pd.to_datetime(df['tpep_pickup_datetime'])).dt.total_seconds() / 60.0
    mask = (
        (df['fare_amount'] > 0) &
        (df['trip_distance'] > 0) &
        (df['trip_distance'] <= 100) &
        (df['duration_min'] >= 1) &
        (df['duration_min'] <= 180) &
        (df['PULocationID'] >= 1) & (df['PULocationID'] <= 263) &
        (df['DOLocationID'] >= 1) & (df['DOLocationID'] <= 263)
    )
    clean_df = df[mask].copy()
    print(f"  Valid trips for analytics: {len(clean_df):,} rows")
    return clean_df, zones

def compute_revenue_and_tips(df):
    print("\n" + "=" * 60)
    print("2. PHÂN TÍCH DOANH THU & TIỀN TIP (REVENUE & TIP ANALYTICS)")
    print("=" * 60)
    
    dt = pd.to_datetime(df['tpep_pickup_datetime'])
    df['pickup_hour'] = dt.dt.hour
    df['pickup_dow'] = dt.dt.day_name()
    df['fare_per_mile'] = (df['fare_amount'] / df['trip_distance']).round(2)
    
    # Tính tip_percent cho các chuyến trả bằng thẻ (payment_type == 1)
    df['tip_pct'] = np.where(
        (df['payment_type'] == 1) & (df['fare_amount'] > 0),
        (df['tip_amount'] / df['fare_amount']) * 100,
        np.nan
    )
    
    # 2.1 Doanh thu & Tip theo giờ
    hourly = df.groupby('pickup_hour').agg(
        total_trips=('fare_amount', 'count'),
        avg_fare=('fare_amount', 'mean'),
        avg_tip=('tip_amount', 'mean'),
        avg_tip_pct=('tip_pct', 'mean'),
        avg_total=('total_amount', 'mean'),
        avg_fare_per_mile=('fare_per_mile', 'median')
    ).reset_index()
    
    hourly = hourly.round(2)
    h_dir = os.path.join(OUT_SQL_DIR, "q6_revenue_tips")
    os.makedirs(h_dir, exist_ok=True)
    hourly_path = os.path.join(h_dir, "revenue_by_hour.csv")
    hourly.to_csv(hourly_path, index=False)
    print(f"  ✅ Saved: {hourly_path} ({len(hourly)} hours)")

    # 2.2 Phân tích theo hình thức thanh toán
    pay = df.groupby('payment_type').agg(
        trip_count=('fare_amount', 'count'),
        avg_fare=('fare_amount', 'mean'),
        avg_tip=('tip_amount', 'mean'),
        avg_total=('total_amount', 'mean'),
        total_revenue=('total_amount', 'sum')
    ).reset_index()
    pay['payment_name'] = pay['payment_type'].map(PAYMENT_MAP).fillna("Khác")
    pay['pct_of_trips'] = ((pay['trip_count'] / len(df)) * 100).round(1)
    pay = pay.round(2)
    pay_path = os.path.join(h_dir, "revenue_by_payment.csv")
    pay.to_csv(pay_path, index=False)
    print(f"  ✅ Saved: {pay_path} ({len(pay)} payment types)")

def compute_od_corridors(df, zones):
    print("\n" + "=" * 60)
    print("3. PHÂN TÍCH CUNG ĐƯỜNG VÀNG (ORIGIN - DESTINATION CORRIDORS)")
    print("=" * 60)
    
    zone_dict = zones.set_index('LocationID')[['Borough', 'Zone']].to_dict(orient='index')
    
    # Gom nhóm theo cặp (PULocationID, DOLocationID)
    od = df.groupby(['PULocationID', 'DOLocationID']).agg(
        trip_count=('fare_amount', 'count'),
        avg_distance=('trip_distance', 'mean'),
        avg_fare=('fare_amount', 'mean'),
        total_revenue=('total_amount', 'sum'),
        avg_duration_min=('duration_min', 'mean')
    ).reset_index()
    
    # Map tên Zone và Borough
    od['pu_zone'] = od['PULocationID'].apply(lambda x: zone_dict.get(x, {}).get('Zone', f'Zone {x}'))
    od['pu_borough'] = od['PULocationID'].apply(lambda x: zone_dict.get(x, {}).get('Borough', 'Unknown'))
    od['do_zone'] = od['DOLocationID'].apply(lambda x: zone_dict.get(x, {}).get('Zone', f'Zone {x}'))
    od['do_borough'] = od['DOLocationID'].apply(lambda x: zone_dict.get(x, {}).get('Borough', 'Unknown'))
    
    od = od.sort_values(by='trip_count', ascending=False)
    
    # 3.1 Top 25 Cung đường vàng
    top25 = od.head(25).copy()
    top25['avg_distance'] = top25['avg_distance'].round(2)
    top25['avg_fare'] = top25['avg_fare'].round(2)
    top25['avg_duration_min'] = top25['avg_duration_min'].round(1)
    top25['total_revenue'] = top25['total_revenue'].round(0)
    
    od_dir = os.path.join(OUT_SQL_DIR, "q7_od_corridors")
    os.makedirs(od_dir, exist_ok=True)
    top_path = os.path.join(od_dir, "top_corridors.csv")
    top25.to_csv(top_path, index=False)
    print(f"  ✅ Saved: {top_path} (Top 25 Golden Corridors)")
    print(f"     Top 1: {top25.iloc[0]['pu_zone']} -> {top25.iloc[0]['do_zone']} ({top25.iloc[0]['trip_count']:,} trips)")

    # 3.2 Luồng di chuyển giữa các Quận (Borough Matrix)
    boro_matrix = od.groupby(['pu_borough', 'do_borough']).agg(
        total_trips=('trip_count', 'sum'),
        total_revenue=('total_revenue', 'sum'),
        avg_fare=('avg_fare', 'mean')
    ).reset_index()
    boro_matrix['pct_trips'] = ((boro_matrix['total_trips'] / boro_matrix['total_trips'].sum()) * 100).round(2)
    boro_matrix = boro_matrix.sort_values(by='total_trips', ascending=False).round(2)
    
    boro_path = os.path.join(od_dir, "borough_matrix.csv")
    boro_matrix.to_csv(boro_path, index=False)
    print(f"  ✅ Saved: {boro_path} (Inter-borough movement matrix)")

def train_multizone_xgboost():
    print("\n" + "=" * 60)
    print("4. HUẤN LUYỆN XGBOOST CHO TOP 5 KHU VỰC TRỌNG ĐIỂM")
    print("=" * 60)
    
    demand_path = os.path.join(DATA_DIR, "processed", "demand_features_2025.parquet")
    df = pd.read_parquet(demand_path)
    
    results = {}
    
    for zone_id, zone_name in TOP_ZONES:
        print(f"\n--- Training Zone {zone_id}: {zone_name} ---")
        z = df[df["PULocationID"] == zone_id].copy()
        if len(z) < 100:
            print(f"  Skipping {zone_id} (not enough records)")
            continue
            
        z = z.sort_values(["pickup_date", "pickup_hour"]).reset_index(drop=True)
        for lag in [1, 2, 3, 6, 12, 24, 48, 168]:
            z[f"lag_{lag}h"] = z["demand_count"].shift(lag)
        z["roll_mean_24h"] = z["demand_count"].rolling(24, min_periods=1).mean()
        z["roll_std_24h"] = z["demand_count"].rolling(24, min_periods=1).std().fillna(0)
        z.dropna(inplace=True)
        
        features = [c for c in z.columns if c.startswith("lag_") or c.startswith("roll_")] + [
            "pickup_hour", "pickup_dow", "pickup_month", "is_weekend", "is_rush_hour", "is_holiday"
        ]
        
        n_total = len(z)
        n_train = int(n_total * 0.70)
        n_val = int(n_total * 0.15)
        
        X_train, y_train = z.iloc[:n_train][features], z.iloc[:n_train]["demand_count"]
        X_val, y_val = z.iloc[n_train:n_train+n_val][features], z.iloc[n_train:n_train+n_val]["demand_count"]
        X_test, y_test = z.iloc[n_train+n_val:][features], z.iloc[n_train+n_val:]["demand_count"]
        
        params = {
            "n_estimators": 300,
            "learning_rate": 0.05,
            "max_depth": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "eval_metric": "rmse",
            "early_stopping_rounds": 25,
            "n_jobs": -1
        }
        
        with mlflow.start_run(run_name=f"xgboost_zone_{zone_id}"):
            model = xgb.XGBRegressor(**params)
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            
            y_pred = np.maximum(model.predict(X_test), 0)
            mape = mean_absolute_percentage_error(y_test, y_pred) * 100
            rmse = np.sqrt(np.mean((y_test.values - y_pred) ** 2))
            mae = np.mean(np.abs(y_test.values - y_pred))
            
            mlflow.log_params({"zone_id": zone_id, "zone_name": zone_name, **params})
            mlflow.log_metrics({"mape": round(mape, 2), "rmse": round(rmse, 2), "mae": round(mae, 2)})
            
            # Lưu biểu đồ Actual vs Predicted
            plt.figure(figsize=(12, 4))
            n_show = min(150, len(y_test))
            plt.plot(range(n_show), y_test.values[:n_show], label="Thực tế (Actual)", color="#1f77b4")
            plt.plot(range(n_show), y_pred[:n_show], label="Dự báo AI (Predicted)", color="#ff7f0e", linestyle="--")
            plt.title(f"Dự Báo Nhu Cầu - Zone {zone_id} ({zone_name}) | RMSE={rmse:.1f}, MAE={mae:.1f}")
            plt.xlabel("Khung giờ (Giờ)")
            plt.ylabel("Số chuyến xe / giờ")
            plt.legend()
            plt.tight_layout()
            
            plot_file = os.path.join(PLOTS_DIR, f"xgboost_pred_zone_{zone_id}.png")
            plt.savefig(plot_file, dpi=100)
            plt.close()
            
            results[str(zone_id)] = {
                "name": zone_name,
                "rmse": round(float(rmse), 2),
                "mae": round(float(mae), 2),
                "mape": round(float(mape), 2),
                "plot": plot_file,
                "actual": [int(x) for x in y_test.values[:50]],
                "pred": [round(float(x), 1) for x in y_pred[:50]]
            }
            print(f"  ✅ Zone {zone_id} ({zone_name}): RMSE={rmse:.2f}, MAE={mae:.2f}, MAPE={mape:.1f}%")
            
    summary_path = os.path.join(MODELS_DIR, "multizone_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  ✅ Summary saved to: {summary_path}")

def main():
    clean_df, zones = load_data()
    compute_revenue_and_tips(clean_df)
    compute_od_corridors(clean_df, zones)
    train_multizone_xgboost()
    print("\n" + "=" * 60)
    print("🎉 HOÀN TẤT TOÀN BỘ CÁC MODULE NGHIỆP VỤ BIG DATA CHUYÊN SÂU!")
    print("=" * 60)

if __name__ == "__main__":
    main()
