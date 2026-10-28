"""
Bước 1: Setup HDFS directory structure & Local directories
Chạy: python scripts/01_setup_hdfs.py
"""
import os
import shutil
import subprocess
import sys

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DIRS = [
    "/raw/2025/yellow",
    "/raw/2025/fhv",
    "/raw/weather",
    "/raw/zone",
    "/processed",
    "/output/sql_results",
    "/output/models",
]

LOCAL_DIRS = [
    r"D:\nyc_data\yellow",
    r"D:\nyc_data\processed",
    r"D:\nyc_data\zone",
    r"D:\nyc_data\output\sql_results",
    r"D:\nyc_data\output\models",
    os.path.abspath("./data/yellow"),
    os.path.abspath("./data/processed"),
    os.path.abspath("./data/zone"),
    os.path.abspath("./data/output/sql_results"),
    os.path.abspath("./data/output/models"),
]

def get_hdfs_base_cmd() -> list[str]:
    # Check if docker is available and namenode container is reachable
    if shutil.which("docker"):
        try:
            res = subprocess.run(
                ["docker", "exec", "namenode", "hdfs", "dfs", "-ls", "/"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return ["docker", "exec", "namenode", "hdfs", "dfs"]
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
        return [hdfs_bin, "dfs"]

    return ["hdfs", "dfs"]

HDFS_BASE = get_hdfs_base_cmd()

def hdfs(cmd: list[str]):
    result = subprocess.run(
        HDFS_BASE + cmd,
        capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr

def ensure_local_dirs():
    print("📁  Đảm bảo các thư mục local tồn tại...")
    for d in LOCAL_DIRS:
        try:
            os.makedirs(d, exist_ok=True)
            print(f"  ✅ {d}")
        except Exception as e:
            print(f"  ⚠️ Lỗi tạo {d}: {e}")

def main():
    print("=" * 60)
    print("🏗️  BƯỚC 1: SETUP THƯ MỤC LOCAL & HDFS")
    print(f"   HDFS backend: {' '.join(HDFS_BASE)}")
    print("=" * 60)

    ensure_local_dirs()

    print("\n🗄️  Kiểm tra HDFS namenode...")
    code, out, err = hdfs(["-ls", "/"])
    if code != 0:
        print(f"❌ Không kết nối được HDFS ({err.strip()}).")
        print("   Vui lòng kiểm tra Docker container hoặc Hadoop daemon!")
        sys.exit(1)

    print("✓ HDFS online. Đang tạo thư mục...\n")
    for d in DIRS:
        code, out, err = hdfs(["-mkdir", "-p", d])
        status = "✅" if code == 0 else "⚠️ (có thể đã tồn tại)"
        print(f"  {status}  {d}")

    print("\n📋 Cấu trúc HDFS hiện tại:")
    _, out, _ = hdfs(["-ls", "/"])
    print(out)

    print("🎉 Setup HDFS hoàn tất!")

if __name__ == "__main__":
    main()

