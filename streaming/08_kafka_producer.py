"""
Bước 8: Kafka Producer — Giả lập streaming trip data
Chạy: python streaming/08_kafka_producer.py
Cần cài: pip install kafka-python pyarrow pandas
"""
import json, time, os, sys
import pandas as pd
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

KAFKA_SERVER  = "localhost:9092"
TOPIC         = "nyc_trips"
DATA_FILE     = r"D:\nyc_data\yellow\yellow_tripdata_2025-01.parquet"
RECORDS_LIMIT = 5000    # Gửi 5000 records cho demo
DELAY_SECONDS = 0.02    # 0.02s/record ≈ 50 records/giây

print("=" * 60)
print("🌊 Bước 8: Kafka Producer — Streaming Trip Data")
print(f"   Topic   : {TOPIC}")
print(f"   Records : {RECORDS_LIMIT:,}")
print(f"   Speed   : ~{1/DELAY_SECONDS:.0f} records/giây")
print("=" * 60)

# Kiểm tra file data
if not os.path.exists(DATA_FILE):
    print(f"\n❌ Không tìm thấy: {DATA_FILE}")
    print("   Chạy scripts/02_download_upload.py trước!")
    sys.exit(1)

# Kết nối Kafka
print("\n🔌 Đang kết nối Kafka...")
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: str(k).encode("utf-8"),
        acks="all",
        retries=3
    )
    print(f"✅ Kết nối thành công: {KAFKA_SERVER}")
except NoBrokersAvailable:
    print(f"❌ Không thể kết nối Kafka tại {KAFKA_SERVER}")
    print("   Kiểm tra: docker ps | grep kafka")
    sys.exit(1)

# Đọc dữ liệu
print(f"\n📂 Đọc dữ liệu: {DATA_FILE}")
df = pd.read_parquet(DATA_FILE, columns=[
    "tpep_pickup_datetime", "PULocationID",
    "DOLocationID", "trip_distance", "passenger_count", "total_amount"
]).dropna().head(RECORDS_LIMIT)

print(f"✅ {len(df):,} records sẵn sàng\n")

# Streaming
print("🚀 Bắt đầu gửi messages...\n")
start = time.time()

for i, (_, row) in enumerate(df.iterrows(), 1):
    msg = {
        "pickup_time":  str(row["tpep_pickup_datetime"]),
        "zone_id":      int(row["PULocationID"]),
        "drop_zone":    int(row["DOLocationID"]),
        "distance":     round(float(row["trip_distance"]), 2),
        "passengers":   int(row["passenger_count"]),
        "amount":       round(float(row["total_amount"]), 2),
        "timestamp":    time.time()
    }
    producer.send(TOPIC, key=str(msg["zone_id"]), value=msg)

    if i % 500 == 0:
        elapsed = time.time() - start
        rps = i / elapsed
        print(f"  📤 [{i:,}/{RECORDS_LIMIT:,}] "
              f"Elapsed: {elapsed:.1f}s | Rate: {rps:.0f} rec/s")

    time.sleep(DELAY_SECONDS)

producer.flush()
elapsed = time.time() - start
print(f"\n✅ Hoàn tất! {RECORDS_LIMIT:,} messages gửi trong {elapsed:.1f}s")
print(f"   Topic: {TOPIC}")
print(f"\n💡 Để xem messages, chạy:")
print(f"   docker exec kafka kafka-console-consumer "
      f"--bootstrap-server localhost:9092 --topic {TOPIC} --from-beginning")
