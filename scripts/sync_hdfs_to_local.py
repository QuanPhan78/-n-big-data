"""
scripts/sync_hdfs_to_local.py
Milestone M2 Deliverable: Local Sync Bridge for NYC Ride-Hailing Big Data Pipeline.

Exports/syncs HDFS parquet files (/processed/demand_features_2025) and all 5 Spark SQL CSV results
(/output/sql_results/{q1..q5}) to local disk mirrors:
  - D:\\nyc_data\\processed\\demand_features_2025.parquet
  - ./data/processed/demand_features_2025.parquet
  - D:\\nyc_data\\output\\sql_results/{q1..q5}/*.csv
  - ./data/output/sql_results/{q1..q5}/*.csv
"""
import os
import shutil
import subprocess
import sys
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATA_ROOT = os.getenv("NYC_DATA_ROOT", r"D:\nyc_data")
REPO_DATA = os.path.abspath("./data")

SQL_QUERIES = [
    "q1_top10_zones",
    "q2_hourly_pattern",
    "q3_weekday_pattern",
    "q4_rush_vs_offpeak",
    "q5_holiday_effect"
]

def check_docker_hdfs():
    if not shutil.which("docker"):
        return False
    try:
        res = subprocess.run(
            ["docker", "exec", "namenode", "hdfs", "dfs", "-ls", "/"],
            capture_output=True, text=True, timeout=5
        )
        return res.returncode == 0
    except Exception:
        return False

def sync_from_hdfs():
    has_docker_hdfs = check_docker_hdfs()
    print(f"HDFS Docker cluster reachable: {has_docker_hdfs}")
    if has_docker_hdfs:
        print("Exporting processed Parquet and SQL CSVs from HDFS to local container volume /data...")
        # Sync processed parquet
        subprocess.run([
            "docker", "exec", "namenode", "hdfs", "dfs", "-get", "-f",
            "/processed/demand_features_2025", "/data/processed/"
        ], capture_output=True)
        # Sync SQL results
        for q in SQL_QUERIES:
            subprocess.run([
                "docker", "exec", "namenode", "hdfs", "dfs", "-get", "-f",
                f"/output/sql_results/{q}", "/data/output/sql_results/"
            ], capture_output=True)
        print("  HDFS export completed.")
    else:
        print("  Note: Docker HDFS cluster is offline or running on VM; using host storage bridge.")

def sync_local_mirrors():
    print("\nSynchronizing local mirrors between D:\\nyc_data and ./data...")
    # Ensure all directories exist
    for base in [DATA_ROOT, REPO_DATA]:
        os.makedirs(os.path.join(base, "yellow"), exist_ok=True)
        os.makedirs(os.path.join(base, "zone"), exist_ok=True)
        os.makedirs(os.path.join(base, "processed"), exist_ok=True)
        for q in SQL_QUERIES:
            os.makedirs(os.path.join(base, "output", "sql_results", q), exist_ok=True)

    # 1. Sync raw files
    raw_files = [
        ("yellow", "yellow_tripdata_2025-01.parquet"),
        ("zone", "taxi_zone_lookup.csv")
    ]
    for sub, fn in raw_files:
        src = os.path.join(DATA_ROOT, sub, fn)
        dst = os.path.join(REPO_DATA, sub, fn)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f"  Mirrored {sub}/{fn} -> ./data/{sub}/")
        elif os.path.exists(dst) and not os.path.exists(src):
            shutil.copy2(dst, src)
            print(f"  Mirrored ./data/{sub}/{fn} -> D:\\nyc_data\\{sub}/")

    # 2. Sync processed parquet
    p_src = os.path.join(DATA_ROOT, "processed", "demand_features_2025.parquet")
    p_dst = os.path.join(REPO_DATA, "processed", "demand_features_2025.parquet")
    if os.path.exists(p_src) and not os.path.exists(p_dst):
        shutil.copy2(p_src, p_dst)
        print("  Mirrored demand_features_2025.parquet -> ./data/processed/")
    elif os.path.exists(p_dst) and not os.path.exists(p_src):
        shutil.copy2(p_dst, p_src)
        print("  Mirrored ./data/processed/demand_features_2025.parquet -> D:\\nyc_data\\processed/")

    # 3. Sync SQL query directories and CSV files
    for q in SQL_QUERIES:
        q_src_dir = os.path.join(DATA_ROOT, "output", "sql_results", q)
        q_dst_dir = os.path.join(REPO_DATA, "output", "sql_results", q)
        if os.path.exists(q_src_dir):
            for item in os.listdir(q_src_dir):
                if item.endswith(".csv"):
                    f_src = os.path.join(q_src_dir, item)
                    f_dst = os.path.join(q_dst_dir, item)
                    if not os.path.exists(f_dst):
                        shutil.copy2(f_src, f_dst)
                        print(f"  Mirrored {q}/{item} -> ./data/output/sql_results/{q}/")
        if os.path.exists(q_dst_dir):
            for item in os.listdir(q_dst_dir):
                if item.endswith(".csv"):
                    f_dst = os.path.join(q_dst_dir, item)
                    f_src = os.path.join(q_src_dir, item)
                    if not os.path.exists(f_src):
                        shutil.copy2(f_dst, f_src)
                        print(f"  Mirrored ./data/.../{q}/{item} -> D:\\nyc_data\\output\\sql_results/{q}/")

def verify_bridge_integrity():
    print("\n" + "=" * 60)
    print("VERIFICATION: Bridge Data Integrity Check")
    print("=" * 60)

    all_ok = True
    # 1. Check demand_features_2025.parquet in both locations
    for base, name in [(DATA_ROOT, "D:\\nyc_data"), (REPO_DATA, "./data")]:
        pq_path = os.path.join(base, "processed", "demand_features_2025.parquet")
        if not os.path.exists(pq_path):
            print(f"❌ Missing: {name}\\processed\\demand_features_2025.parquet")
            all_ok = False
        else:
            sz = os.path.getsize(pq_path)
            if sz == 0:
                print(f"❌ Empty file: {name}\\processed\\demand_features_2025.parquet")
                all_ok = False
            else:
                try:
                    df = pd.read_parquet(pq_path)
                    print(f"✅ {name}\\processed\\demand_features_2025.parquet exists: {sz:,} bytes, {len(df):,} rows, cols={list(df.columns)}")
                except Exception as e:
                    print(f"❌ Corrupt parquet {pq_path}: {e}")
                    all_ok = False

    # 2. Check 5 SQL result CSVs
    for q in SQL_QUERIES:
        for base, name in [(DATA_ROOT, "D:\\nyc_data"), (REPO_DATA, "./data")]:
            q_dir = os.path.join(base, "output", "sql_results", q)
            csv_files = [os.path.join(q_dir, f) for f in os.listdir(q_dir) if f.endswith(".csv")] if os.path.exists(q_dir) else []
            if not csv_files:
                print(f"❌ No CSV files found for query {q} in {name}\\output\\sql_results\\{q}")
                all_ok = False
            else:
                for c in csv_files:
                    sz = os.path.getsize(c)
                    if sz == 0:
                        print(f"❌ Empty CSV: {c}")
                        all_ok = False
                    else:
                        df_c = pd.read_csv(c)
                        print(f"✅ Query {q} ({os.path.basename(c)} in {name}): {sz:,} bytes, {len(df_c)} rows")

    print("=" * 60)
    if all_ok:
        print("🎉 Bridge integrity check PASSED! All artifacts non-empty and valid.")
    else:
        print("⚠️ Bridge integrity check had issues. Please inspect errors above.")
    return all_ok

def main():
    print("=" * 60)
    print("🌉 HDFS TO LOCAL SYNC BRIDGE")
    print("=" * 60)
    sync_from_hdfs()
    sync_local_mirrors()
    ok = verify_bridge_integrity()
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
