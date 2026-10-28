"""
Bước 5: Spark SQL — 5 câu truy vấn phân tích
Chạy: docker exec spark-master spark-submit /opt/bitnami/spark/jobs/05_spark_sql.py
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("NYC_Step5_SQL") \
    .master("local[*]") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .config("spark.hadoop.dfs.replication", "2") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("\n" + "="*60)
print("🔍 Bước 5: Spark SQL — Phân tích Nhu cầu Gọi xe")
print("="*60)

demand = spark.read.parquet("hdfs://namenode:9000/processed/demand_features_2025")
demand.createOrReplaceTempView("demand")
print(f"\n✅ Đã load demand matrix: {demand.count():,} dòng\n")

# ============================================
QUERIES = {
    "q1_top10_zones": {
        "title": "🏆 Q1: Top 10 Zone có nhu cầu cao nhất (2025)",
        "sql": """
            SELECT
                PULocationID                        AS zone_id,
                SUM(demand_count)                   AS total_trips,
                ROUND(AVG(demand_count), 1)         AS avg_hourly_demand,
                MAX(demand_count)                   AS peak_demand
            FROM demand
            GROUP BY PULocationID
            ORDER BY total_trips DESC
            LIMIT 10
        """
    },
    "q2_hourly_pattern": {
        "title": "⏰ Q2: Phân bố nhu cầu theo giờ trong ngày",
        "sql": """
            SELECT
                pickup_hour,
                ROUND(AVG(demand_count), 1)     AS avg_demand,
                MAX(demand_count)               AS peak_demand,
                CASE
                    WHEN pickup_hour IN (7,8,9,17,18,19,20) THEN 'Rush Hour'
                    WHEN pickup_hour BETWEEN 23 AND 24
                      OR pickup_hour BETWEEN 0 AND 5 THEN 'Late Night'
                    ELSE 'Normal'
                END                             AS period_type
            FROM demand
            GROUP BY pickup_hour
            ORDER BY pickup_hour
        """
    },
    "q3_weekday_pattern": {
        "title": "📅 Q3: Nhu cầu theo ngày trong tuần",
        "sql": """
            SELECT
                pickup_dow,
                CASE pickup_dow
                    WHEN 1 THEN 'Chủ nhật'
                    WHEN 2 THEN 'Thứ 2'
                    WHEN 3 THEN 'Thứ 3'
                    WHEN 4 THEN 'Thứ 4'
                    WHEN 5 THEN 'Thứ 5'
                    WHEN 6 THEN 'Thứ 6'
                    WHEN 7 THEN 'Thứ 7'
                END                             AS ten_ngay,
                ROUND(AVG(demand_count), 1)     AS avg_demand,
                SUM(demand_count)               AS total_trips
            FROM demand
            GROUP BY pickup_dow
            ORDER BY pickup_dow
        """
    },
    "q4_rush_vs_offpeak": {
        "title": "🚦 Q4: Rush Hour vs Off-Peak",
        "sql": """
            SELECT
                CASE is_rush_hour
                    WHEN 1 THEN 'Rush Hour (7-9h, 17-20h)'
                    ELSE 'Off-Peak'
                END                                 AS period,
                COUNT(DISTINCT pickup_date)         AS num_days,
                ROUND(AVG(demand_count), 1)         AS avg_demand,
                SUM(demand_count)                   AS total_trips
            FROM demand
            GROUP BY is_rush_hour
            ORDER BY is_rush_hour DESC
        """
    },
    "q5_holiday_effect": {
        "title": "🎉 Q5: Tác động của ngày lễ lên nhu cầu",
        "sql": """
            SELECT
                CASE is_holiday
                    WHEN 1 THEN 'Ngày lễ'
                    ELSE 'Ngày thường'
                END                                 AS loai_ngay,
                COUNT(DISTINCT pickup_date)         AS so_ngay,
                ROUND(AVG(demand_count), 1)         AS avg_demand,
                MAX(demand_count)                   AS peak_demand
            FROM demand
            GROUP BY is_holiday
            ORDER BY is_holiday DESC
        """
    }
}
# ============================================

for name, q in QUERIES.items():
    print(f"\n{q['title']}")
    print("-" * 50)
    result = spark.sql(q["sql"])
    result.show(20, truncate=False)

    # Lưu CSV vào HDFS
    result.coalesce(1).write.mode("overwrite").csv(
        f"hdfs://namenode:9000/output/sql_results/{name}",
        header=True
    )
    print(f"   💾 Đã lưu: /output/sql_results/{name}")

print("\n" + "="*60)
print("✅ Bước 5 hoàn tất! 5 queries đã chạy và lưu vào HDFS.")
print("="*60)
spark.stop()
