# Project: NYC Ridehailing Big Data Pipeline (2025)

## Architecture
- **Infrastructure Layer**: Docker Compose running on host, containing:
  - HDFS Cluster: 1 NameNode (port 9870, 9000) + 2 DataNodes (`datanode`, `datanode2` with dedicated volumes).
  - Spark Cluster: 1 Spark Master (port 8080, 7077) + 1 Spark Worker (port 8081).
  - MLflow Server: Tracking & Model Registry (port 5000) backed by SQLite DB (`sqlite:////mlflow/mlflow.db`) and artifact store.
  - Streaming: Zookeeper (port 2181) + Kafka Broker (port 9092 with KAFKA_LISTENERS 0.0.0.0:9092).
  - Orchestration: Airflow 2.9.1 (port 8081) with SequentialExecutor & SQLite DB.
  - Visualization: Streamlit Dashboard (port 8501 with headless mode and folium plugins).
- **Data Ingestion & Storage Layer**:
  - TLC Yellow Taxi 2025 data downloaded from CloudFront CDN to local cache and uploaded to HDFS `/raw/2025/yellow`.
  - Zone lookup CSV uploaded to HDFS `/raw/zone`.
- **Compute Layer**:
  - PySpark ETL: cleans, filters, adds temporal/holiday/rush-hour features, creates aggregated demand matrix, writes Parquet with dfs.replication=2 to `hdfs://namenode:9000/processed/demand_features_2025`.
  - Spark SQL: runs 5 analytical queries (`q1_top10_zones`, `q2_hourly_pattern`, `q3_weekday_pattern`, `q4_rush_vs_offpeak`, `q5_holiday_effect`) saving to `hdfs://namenode:9000/output/sql_results/{q1..q5}`.
  - Data Sync Bridge: exports Parquet and SQL outputs from HDFS to local path for ML scripts and Streamlit.
- **Machine Learning & Streaming Layer**:
  - Dynamic chronological train/val/test splits (70/15/15) handling available 2025 data.
  - XGBoost regressor predicting pickup demand, logged to MLflow with metrics (RMSE, MAE, R2, MAPE) and registered in MLflow Model Registry (`nyc_demand_xgboost`).
  - Prophet baseline model trained and logged to MLflow.
  - Kafka producer streaming simulated real-time trip events to topic `nyc_trips`; Kafka consumer processing stream.
- **Presentation & Orchestration Layer**:
  - Airflow DAG orchestrating end-to-end pipeline tasks.
  - Streamlit dashboard rendering KPIs, spatial demand maps, SQL analytical graphs, ML forecasts, and streaming metrics.
  - Verification Suite: `verify_infrastructure.py` (port checks) and `verify_data.py` (HDFS checks).

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| F1 | Multi-DataNode HDFS | Docker compose configuration with 1 NameNode and 2 DataNodes | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Core Docker Stack | Startup and health validation of HDFS, Spark, MLflow, Kafka, Airflow | M1 | ORIGINAL_REQUEST §R1 |
| F3 | MLflow SQLite Backend | Configure MLflow server with SQLite store to enable Model Registry | M1 | Survey (Explorer 1 & 3) |
| F4 | Streamlit Service Provisioning | Ensure Streamlit dashboard runs on port 8501 without errors | M1, M4 | ORIGINAL_REQUEST §R1, §R4 |
| F5 | HDFS Directory Setup | Automatic creation of required HDFS directory hierarchy | M2 | ORIGINAL_REQUEST §R2 |
| F6 | TLC 2025 Data Ingestion | Download TLC Jan-Mar 2025 Parquet and upload to HDFS | M2 | ORIGINAL_REQUEST §R2 |
| F7 | PySpark Demand ETL | ETL pipeline creating `demand_features_2025` in HDFS | M2 | ORIGINAL_REQUEST §R2 |
| F8 | Spark SQL 5-Query Analytics | 5 SQL queries producing CSV results in HDFS `/output/sql_results/` | M2 | ORIGINAL_REQUEST §R2 |
| F9 | HDFS to Local Data Bridge | Sync/export HDFS processed Parquet and SQL results to local disk | M2 | Survey (Explorer 2 & 3) |
| F10 | Dynamic ML Data Splitting | Chronological percentile splits (70/15/15) avoiding empty datasets | M3 | Survey (Explorer 3) |
| F11 | XGBoost Model & MLflow Registry | Train XGBoost, log metrics, register model in MLflow Model Registry | M3 | ORIGINAL_REQUEST §R3 |
| F12 | Prophet Baseline Model | Train Prophet model and log runs/metrics to MLflow | M3 | ORIGINAL_REQUEST §R3 |
| F13 | Kafka Real-Time Streaming | Produce simulated 2025 trip stream to Kafka topic `nyc_trips` and consume | M3 | ORIGINAL_REQUEST §R3 |
| F14 | Airflow DAG Pipeline | Airflow DAG orchestrating the pipeline steps | M4 | ORIGINAL_REQUEST §R4 |
| F15 | Streamlit Interactive Dashboard | Multi-view dashboard rendering demand metrics, SQL charts, ML forecasts | M4 | ORIGINAL_REQUEST §R4 |
| F16 | Infrastructure Verification Script | `verify_infrastructure.py` reporting HTTP 200 on 9870, 8080, 5000, 8501 | M5 | Acceptance Criterion 1 |
| F17 | HDFS Data Verification Script | `verify_data.py` verifying `demand_features_2025` and 5 SQL dirs > 0 | M5 | Acceptance Criterion 2 |
| F18 | MLflow Model Verification | Programmatic check verifying XGBoost model registered in MLflow registry | M5 | Acceptance Criterion 3 |
| F19 | Streamlit Curl Verification | Verification that `curl http://localhost:8501` returns HTML without stack traces | M5 | Acceptance Criterion 4 |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Docker Infrastructure Setup | F1, F2, F3, F4 (Update docker-compose.yml: 1 NN + 2 DN, MLflow SQLite DB, Airflow config, start services & verify healthy) | none | DONE |
| M2 | Data Pipeline Execution & Bridge | F5, F6, F7, F8, F9 (Run setup_hdfs, download TLC 2025 data, run PySpark ETL & Spark SQL to HDFS, export bridge to local) | M1 | IN_PROGRESS |
| M3 | Machine Learning & Kafka Streaming | F10, F11, F12, F13 (Update ML dynamic splits, train XGBoost & Prophet, register in MLflow, run Kafka streaming) | M2 | PLANNED |
| M4 | Airflow Orchestration & Streamlit | F14, F15 (Activate & verify Airflow DAG, launch & verify Streamlit dashboard with visualizations) | M2, M3 | PLANNED |
| M5 | Acceptance Verification & E2E Audit | F16, F17, F18, F19 (Author verify_infrastructure.py, verify_data.py, execute all 4 AC programmatic checks, post-victory audit) | M1, M2, M3, M4 | PLANNED |

---

## Interface Contracts
### Data Pipeline ↔ Machine Learning
- Output Parquet path in HDFS: `hdfs://namenode:9000/processed/demand_features_2025`
- Exported local Parquet path: `D:\nyc_data\processed\demand_features_2025.parquet` (and `./data/processed/demand_features_2025.parquet`)
- Schema: `PULocationID` (int), `pickup_date` (string/date), `pickup_hour` (int), `pickup_dow` (int), `pickup_month` (int), `is_weekend` (int), `is_rush_hour` (int), `is_holiday` (int), `demand_count` (bigint), `avg_distance` (double), `avg_duration_min` (double).

### Data Pipeline ↔ Streamlit Dashboard
- HDFS SQL Results: `hdfs://namenode:9000/output/sql_results/q1_top10_zones`, `.../q2_hourly_pattern`, `.../q3_weekday_pattern`, `.../q4_rush_vs_offpeak`, `.../q5_holiday_effect`
- Local SQL Results: `data/output/sql_results/{q1..q5}/*.csv`
- Dashboard reads CSVs with fallback handling and displays charts.

### MLflow Service ↔ ML Training
- Tracking URI: `http://localhost:5000`
- Backend DB: `sqlite:////mlflow/mlflow.db`
- Registered Model Name: `nyc_demand_xgboost`

### Streaming Producer ↔ Consumer
- Kafka Broker: `localhost:9092`
- Topic: `nyc_trips`
- Payload: JSON with `pickup_time`, `zone_id`, `drop_zone`, `distance`, `passengers`, `amount`, `timestamp`.

---

## Code Layout
- `docker-compose.yml`: Infrastructure services definition (NameNode, DataNode 1 & 2, Spark Master & Worker, MLflow, Kafka, Airflow, Streamlit).
- `scripts/`:
  - `scripts/01_setup_hdfs.py`: HDFS directory initialization.
  - `scripts/02_download_upload.py`: Data download & HDFS upload.
  - `scripts/sync_hdfs_to_local.py`: Export bridge from HDFS to local disk.
  - `scripts/verify_docker_compose.py`: Compose validation script.
  - `scripts/test_m1_challenger.py`: Adversarial empirical verification suite.
  - `scripts/start_stack.ps1` & `start_stack.sh`: Infrastructure launchers.
- `spark/`:
  - `spark/03_read_spark.py`: Spark connectivity validation.
  - `spark/04_etl_clean.py`: PySpark feature engineering & demand matrix aggregation.
  - `spark/05_spark_sql.py`: Spark SQL analytical queries.
- `ml/`:
  - `ml/06_xgboost_model.py`: XGBoost training and MLflow registration.
  - `ml/06_prophet_model.py`: Prophet baseline training.
- `streaming/`:
  - `streaming/08_kafka_producer.py`: Kafka streaming producer.
  - `streaming/08_kafka_consumer.py`: Kafka streaming consumer.
- `airflow/`:
  - `airflow/dags/nyc_pipeline.py`: Airflow orchestration DAG.
- `dashboard/`:
  - `dashboard/app.py`: Streamlit dashboard application.
- `verify_infrastructure.py`: Programmatic AC1 verification script (ports 9870, 8080, 5000, 8501).
- `verify_data.py`: Programmatic AC2 verification script (HDFS demand features and 5 SQL results).
