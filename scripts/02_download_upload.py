"""
Bước 2: Download NYC TLC 2025 + Zone lookup → Upload lên HDFS
Chạy: python scripts/02_download_upload.py

Mặc định tải Jan 2025 (~59MB) theo yêu cầu Milestone M2.
Có thể cấu hình thêm tháng qua biến môi trường NYC_MONTHS hoặc tham số dòng lệnh.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# =====================================================
# CẤU HÌNH
# =====================================================
env_months = os.getenv("NYC_MONTHS")
if env_months:
    MONTHS_TO_DOWNLOAD = [m.strip() for m in env_months.split(",") if m.strip()]
elif len(sys.argv) > 1:
    MONTHS_TO_DOWNLOAD = sys.argv[1:]
else:
    # Mặc định tháng 2025-01 (~59MB) theo yêu cầu Milestone M2
    MONTHS_TO_DOWNLOAD = ["2025-01"]

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
DATA_ROOT = os.getenv("NYC_DATA_ROOT", r"D:\nyc_data")

os.makedirs(os.path.join(DATA_ROOT, "yellow"), exist_ok=True)
os.makedirs(os.path.join(DATA_ROOT, "zone"),   exist_ok=True)

# Also ensure ./data mirroring
LOCAL_REPO_DATA = os.path.abspath("./data")
os.makedirs(os.path.join(LOCAL_REPO_DATA, "yellow"), exist_ok=True)
os.makedirs(os.path.join(LOCAL_REPO_DATA, "zone"), exist_ok=True)

def get_hdfs_runner():
    # Check if docker is available and namenode container is reachable
    if shutil.which("docker"):
        try:
            res = subprocess.run(
                ["docker", "exec", "namenode", "hdfs", "dfs", "-ls", "/"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return "docker"
        except Exception:
            pass

    # Check native hdfs
    hdfs_bin = shutil.which("hdfs") or shutil.which("hdfs.cmd")
    if not hdfs_bin and "HADOOP_HOME" in os.environ:
        cand = os.path.join(os.environ["HADOOP_HOME"], "bin", "hdfs.cmd")
        if os.path.exists(cand):
            hdfs_bin = cand
        else:
            cand2 = os.path.join(os.environ["HADOOP_HOME"], "bin", "hdfs")
            if os.path.exists(cand2):
                hdfs_bin = cand2

    if hdfs_bin:
        return hdfs_bin

    return "hdfs"

HDFS_RUNNER = get_hdfs_runner()

def progress_hook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(downloaded / total_size * 100, 100)
        mb  = downloaded / 1_000_000
        print(f"\r   {pct:5.1f}%  {mb:.1f} MB", end="", flush=True)

def download(url: str, dest: str) -> bool:
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        size_mb = os.path.getsize(dest) / 1_000_000
        print(f"   ⏩ Đã có sẵn: {dest} ({size_mb:.1f} MB)")
        return True
    print(f"   ⬇  {url}")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print()  # newline sau progress
        return True
    except Exception as e:
        print(f"\n   ❌ Lỗi: {e}")
        return False

def hdfs_put(local_rel_path: str, hdfs_dir: str):
    """Copy file từ local lên HDFS (hỗ trợ cả Docker lẫn native Hadoop CLI)."""
    local_abs_path = os.path.join(DATA_ROOT, local_rel_path)
    if not os.path.exists(local_abs_path):
        print(f"   ⚠️  Không tìm thấy local file: {local_abs_path}")
        return False

    if HDFS_RUNNER == "docker":
        fname = os.path.basename(local_rel_path)
        subdir = os.path.dirname(local_rel_path).replace("\\", "/")
        container_path = f"/data/{subdir}/{fname}".replace("//", "/")
        cmd = ["docker", "exec", "namenode", "hdfs", "dfs", "-put", "-f", container_path, hdfs_dir]
    else:
        cmd = [HDFS_RUNNER, "dfs", "-put", "-f", local_abs_path, hdfs_dir]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   📤 HDFS: {hdfs_dir} ({os.path.basename(local_abs_path)})")
        return True
    else:
        print(f"   ⚠️  HDFS upload lỗi: {result.stderr.strip()}")
        return False

def hdfs_ls(hdfs_path: str):
    if HDFS_RUNNER == "docker":
        cmd = ["docker", "exec", "namenode", "hdfs", "dfs", "-ls", hdfs_path]
    else:
        cmd = [HDFS_RUNNER, "dfs", "-ls", hdfs_path]
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    print("=" * 60)
    print("📦 NYC TLC 2025 — Download & Upload lên HDFS")
    print(f"   💾 Lưu local tại: {DATA_ROOT}")
    print(f"   ⚡ HDFS runner: {HDFS_RUNNER}")
    print("=" * 60)

    # --- Yellow Taxi ---
    print(f"\n🟡 Yellow Taxi ({len(MONTHS_TO_DOWNLOAD)} tháng: {', '.join(MONTHS_TO_DOWNLOAD)})")
    for month in MONTHS_TO_DOWNLOAD:
        fname = f"yellow_tripdata_{month}.parquet"
        dest  = os.path.join(DATA_ROOT, "yellow", fname)
        repo_dest = os.path.join(LOCAL_REPO_DATA, "yellow", fname)
        print(f"\n[{month}] {fname}")
        ok = download(f"{BASE_URL}/{fname}", dest)
        if ok:
            # Sync to local repo path if different
            if os.path.abspath(dest) != os.path.abspath(repo_dest) and not os.path.exists(repo_dest):
                try:
                    shutil.copy2(dest, repo_dest)
                except Exception:
                    pass
            hdfs_put(f"yellow/{fname}", "/raw/2025/yellow/")

    # --- Zone Lookup ---
    print("\n🗺️  Zone Lookup CSV")
    zone_url  = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    zone_dest = os.path.join(DATA_ROOT, "zone", "taxi_zone_lookup.csv")
    zone_repo_dest = os.path.join(LOCAL_REPO_DATA, "zone", "taxi_zone_lookup.csv")
    if download(zone_url, zone_dest):
        if os.path.abspath(zone_dest) != os.path.abspath(zone_repo_dest) and not os.path.exists(zone_repo_dest):
            try:
                shutil.copy2(zone_dest, zone_repo_dest)
            except Exception:
                pass
        hdfs_put("zone/taxi_zone_lookup.csv", "/raw/zone/")

    # --- Verify ---
    print("\n" + "=" * 60)
    print("✅ Xác nhận dữ liệu trên HDFS:")
    res_yellow = hdfs_ls("/raw/2025/yellow/")
    print("📁 /raw/2025/yellow/:")
    print(res_yellow.stdout)

    res_zone = hdfs_ls("/raw/zone/")
    print("📁 /raw/zone/:")
    print(res_zone.stdout)

    print("=" * 60)
    print("🎉 Bước 2 hoàn tất!\n")

if __name__ == "__main__":
    main()

