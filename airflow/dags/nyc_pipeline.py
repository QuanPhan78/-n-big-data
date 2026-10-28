from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging

# ============================================================
# Bước 9: Airflow DAG — NYC Ride-Hailing Pipeline
# Truy cập Airflow UI: http://localhost:8081
# Login: admin / admin
# ============================================================

default_args = {
    "owner":            "nyc-team",
    "retries":          1,
    "retry_delay":      timedelta(minutes=2),
    "email_on_failure": False,
}

with DAG(
    dag_id="nyc_ridehailing_pipeline",
    description="NYC TLC 2025 — Full Big Data Pipeline (9 bước)",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,    # Trigger thủ công (None = không tự động)
    catchup=False,
    default_args=default_args,
    tags=["bigdata", "nyc", "spark", "kafka"],
) as dag:

    # ---- Task 1: Khởi tạo HDFS ----
    t1_setup_hdfs = BashOperator(
        task_id="setup_hdfs",
        bash_command="python /opt/scripts/01_setup_hdfs.py",
        doc_md="Tạo cấu trúc thư mục HDFS: raw/, processed/, output/"
    )

    # ---- Task 2: Download & Upload dữ liệu ----
    t2_download = BashOperator(
        task_id="download_and_upload_data",
        bash_command="python /opt/scripts/02_download_upload.py",
        execution_timeout=timedelta(hours=2),
        doc_md="Tải NYC TLC Parquet 2025 và upload lên HDFS raw/"
    )

    # ---- Task 3: PySpark đọc & validate ----
    t3_validate = BashOperator(
        task_id="validate_raw_data",
        bash_command=(
            "spark-submit "
            "--master local[2] "
            "--driver-memory 2g "
            "/opt/spark/03_read_spark.py"
        ),
        doc_md="Kiểm tra schema và row count dữ liệu thô"
    )

    # ---- Task 4: ETL Cleaning ----
    t4_etl = BashOperator(
        task_id="spark_etl_cleaning",
        bash_command=(
            "spark-submit "
            "--master local[2] "
            "--driver-memory 3g "
            "/opt/spark/04_etl_clean.py"
        ),
        execution_timeout=timedelta(minutes=30),
        doc_md="Làm sạch, feature engineering, aggregate demand matrix"
    )

    # ---- Task 5: Spark SQL Analysis ----
    t5_sql = BashOperator(
        task_id="spark_sql_analysis",
        bash_command=(
            "spark-submit "
            "--master local[2] "
            "--driver-memory 2g "
            "/opt/spark/05_spark_sql.py"
        ),
        doc_md="5 câu SQL phân tích: top zone, giờ cao điểm, tuần, v.v."
    )

    # ---- Task 6: Train XGBoost ----
    t6_train = BashOperator(
        task_id="train_xgboost_model",
        bash_command="python /opt/ml/06_xgboost_model.py",
        execution_timeout=timedelta(minutes=20),
        doc_md="Huấn luyện XGBoost forecasting model + log vào MLflow"
    )

    # ---- Task 7: Train Prophet (chạy song song với XGBoost) ----
    t7_prophet = BashOperator(
        task_id="train_prophet_baseline",
        bash_command="python /opt/ml/06_prophet_model.py",
        execution_timeout=timedelta(minutes=15),
        doc_md="Huấn luyện Prophet baseline + log vào MLflow"
    )

    # ---- Dependency graph ----
    # t1 → t2 → t3 → t4 → t5 → [t6, t7] (song song)
    t1_setup_hdfs >> t2_download >> t3_validate >> t4_etl >> t5_sql >> [t6_train, t7_prophet]
