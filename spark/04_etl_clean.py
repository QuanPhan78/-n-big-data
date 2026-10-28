"""
Bước 4: Làm sạch dữ liệu + Feature Engineering + Aggregate Demand Matrix
Chạy: docker exec spark-master spark-submit /opt/bitnami/spark/jobs/04_etl_clean.py
"""
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder \
    .appName("NYC_Step4_ETL") \
    .master("local[*]") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .config("spark.hadoop.dfs.replication", "2") \
    .config("spark.driver.memory", "3g") \
    .config("spark.sql.shuffle.partitions", "8") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("\n" + "="*60)
print("🧹 Bước 4: ETL - Làm sạch & Feature Engineering")
print("="*60)

# ============================================
# LOAD
# ============================================
df = spark.read.parquet("hdfs://namenode:9000/raw/2025/yellow/")
raw_count = df.count()
print(f"\n📥 Dữ liệu gốc: {raw_count:,} dòng")

# ============================================
# LÀM SẠCH (Cleaning)
# ============================================
df_clean = df.filter(
    (F.col("trip_distance") > 0) &                    # Khoảng cách > 0
    (F.col("passenger_count") >= 1) &                  # Ít nhất 1 khách
    (F.col("PULocationID").between(1, 263)) &           # Zone hợp lệ NYC
    (F.col("tpep_pickup_datetime").isNotNull()) &       # Có thời gian đón
    (F.col("tpep_dropoff_datetime").isNotNull())        # Có thời gian trả
).withColumn(
    "duration_min",
    (F.unix_timestamp("tpep_dropoff_datetime") -
     F.unix_timestamp("tpep_pickup_datetime")) / 60
).filter(
    (F.col("duration_min") >= 1) &    # Chuyến ít nhất 1 phút
    (F.col("duration_min") <= 240)    # Chuyến tối đa 4 giờ
)

clean_count = df_clean.count()
pct_kept = clean_count / raw_count * 100
print(f"🧹 Sau làm sạch : {clean_count:,} dòng ({pct_kept:.1f}% giữ lại)")

if pct_kept < 80:
    print(f"⚠️  Cảnh báo: chỉ giữ lại {pct_kept:.1f}% — filter có thể quá chặt!")
else:
    print(f"✅ Tỷ lệ giữ lại hợp lý (≥ 80%)")

# ============================================
# FEATURE ENGINEERING
# ============================================
HOLIDAYS_2025 = [
    "2025-01-01",  # New Year's Day
    "2025-01-20",  # MLK Day
    "2025-02-17",  # Presidents' Day
    "2025-05-26",  # Memorial Day
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-11-11",  # Veterans Day
    "2025-11-27",  # Thanksgiving
    "2025-12-25",  # Christmas
]

df_feat = df_clean \
    .withColumn("pickup_date",  F.to_date("tpep_pickup_datetime")) \
    .withColumn("pickup_hour",  F.hour("tpep_pickup_datetime")) \
    .withColumn("pickup_dow",   F.dayofweek("tpep_pickup_datetime")) \
    .withColumn("pickup_month", F.month("tpep_pickup_datetime")) \
    .withColumn("is_weekend",
        F.when(F.dayofweek("tpep_pickup_datetime").isin([1, 7]), 1).otherwise(0)) \
    .withColumn("is_rush_hour",
        F.when(
            F.hour("tpep_pickup_datetime").isin([7, 8, 9, 17, 18, 19, 20]), 1
        ).otherwise(0)) \
    .withColumn("is_holiday",
        F.when(
            F.to_date("tpep_pickup_datetime").cast("string").isin(HOLIDAYS_2025), 1
        ).otherwise(0))

print(f"\n✅ Feature engineering xong. Cột mới: pickup_date, pickup_hour, pickup_dow,")
print(f"   pickup_month, is_weekend, is_rush_hour, is_holiday")

# ============================================
# AGGREGATE → DEMAND MATRIX
# ============================================
demand = df_feat.groupBy(
    "PULocationID",
    "pickup_date",
    "pickup_hour",
    "pickup_dow",
    "pickup_month",
    "is_weekend",
    "is_rush_hour",
    "is_holiday"
).agg(
    F.count("*").alias("demand_count"),
    F.avg("trip_distance").alias("avg_distance"),
    F.avg("duration_min").alias("avg_duration_min")
).orderBy("pickup_date", "pickup_hour", "PULocationID")

demand_count = demand.count()
zones_count  = demand.select("PULocationID").distinct().count()
print(f"\n📊 Demand matrix:")
print(f"   Số dòng  : {demand_count:,}")
print(f"   Số zone  : {zones_count} (kỳ vọng tối đa 263)")

print("\n🔍 Mẫu demand matrix:")
demand.show(10)

# ============================================
# LƯU VÀO HDFS
# ============================================
output_path = "hdfs://namenode:9000/processed/demand_features_2025"
demand.write.mode("overwrite").parquet(output_path)
print(f"\n💾 Đã lưu: {output_path}")

print("\n" + "="*60)
print("✅ Bước 4 hoàn tất!")
print("="*60)
spark.stop()
