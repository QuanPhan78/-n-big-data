"""
Bước 3: PySpark đọc dữ liệu từ HDFS và kiểm tra schema
Chạy từ container:
  docker exec spark-master spark-submit /opt/bitnami/spark/jobs/03_read_spark.py
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("NYC_Step3_Read") \
    .master("local[*]") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("\n" + "="*60)
print("📖 Bước 3: Đọc dữ liệu NYC TLC từ HDFS")
print("="*60)

df = spark.read.parquet("hdfs://namenode:9000/raw/2025/yellow/")

print(f"\n✅ Đọc thành công!")
print(f"   Số dòng  : {df.count():>12,}")
print(f"   Số cột   : {len(df.columns):>12}")

print("\n📋 Schema:")
df.printSchema()

print("\n📊 Thống kê cột quan trọng:")
df.select(
    "tpep_pickup_datetime",
    "PULocationID",
    "trip_distance",
    "passenger_count",
    "total_amount"
).describe().show()

print("\n🔍 5 dòng mẫu:")
df.select(
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_distance",
    "passenger_count",
    "total_amount"
).show(5, truncate=False)

# Kiểm tra giá trị null
print("🔎 Kiểm tra NULL:")
from pyspark.sql import functions as F
null_counts = df.select([
    F.count(F.when(F.col(c).isNull(), c)).alias(c)
    for c in ["tpep_pickup_datetime", "PULocationID", "trip_distance"]
])
null_counts.show()

print("="*60)
print("✅ Bước 3 hoàn tất! Paste output cho mentor để xác nhận.")
print("="*60)
spark.stop()
