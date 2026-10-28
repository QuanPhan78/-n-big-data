#!/usr/bin/env python3
"""
Verification script for docker-compose.yml configuration (Milestone M1).
Validates all required service definitions, volumes, ports, and environment variables.
"""
import sys
import yaml
from pathlib import Path

def test_docker_compose_config():
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists(), "docker-compose.yml does not exist"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    volumes = config.get("volumes", {})

    print(f"Loaded docker-compose.yml: {len(services)} services, {len(volumes)} volumes.")

    # 1. HDFS Services
    assert "namenode" in services, "Missing service: namenode"
    assert "datanode" in services, "Missing service: datanode"
    assert "datanode2" in services, "Missing service: datanode2"

    nn_env = services["namenode"].get("environment", [])
    dn1_env = services["datanode"].get("environment", [])
    dn2_env = services["datanode2"].get("environment", [])

    assert any("HDFS_CONF_dfs_replication=2" in str(e) for e in nn_env), "namenode missing HDFS_CONF_dfs_replication=2"
    assert any("HDFS_CONF_dfs_replication=2" in str(e) for e in dn1_env), "datanode missing HDFS_CONF_dfs_replication=2"
    assert any("HDFS_CONF_dfs_replication=2" in str(e) for e in dn2_env), "datanode2 missing HDFS_CONF_dfs_replication=2"

    assert "hadoop_datanode2" in volumes, "Volume hadoop_datanode2 not in volumes section"
    assert any("hadoop_datanode2:" in str(v) for v in services["datanode2"].get("volumes", [])), \
        "datanode2 missing hadoop_datanode2 volume mount"

    # 2. MLflow Service
    assert "mlflow" in services, "Missing service: mlflow"
    mlflow_cmd = services["mlflow"].get("command", "")
    assert "sqlite:////mlflow/mlflow.db" in mlflow_cmd, "MLflow command missing SQLite backend-store-uri"
    assert "--artifacts-destination /mlflow/artifacts" in mlflow_cmd, "MLflow command missing artifacts-destination"
    assert "--serve-artifacts" in mlflow_cmd, "MLflow command missing serve-artifacts"
    assert any("5000:5000" in str(p) for p in services["mlflow"].get("ports", [])), "MLflow port 5000 not exposed"

    # 3. Airflow Service
    assert "airflow" in services, "Missing service: airflow"
    airflow_env = services["airflow"].get("environment", [])
    assert any("AIRFLOW__CORE__EXECUTOR=SequentialExecutor" in str(e) for e in airflow_env), \
        "Airflow missing AIRFLOW__CORE__EXECUTOR=SequentialExecutor"
    airflow_cmd = services["airflow"].get("command", "")
    assert "airflow db migrate" in airflow_cmd, "Airflow command missing 'airflow db migrate'"

    # 4. Streamlit Service
    assert "streamlit" in services, "Missing service: streamlit"
    assert any("8501:8501" in str(p) for p in services["streamlit"].get("ports", [])), "Streamlit port 8501 not exposed"

    # 5. Core Stack Check
    required_services = [
        "namenode", "datanode", "datanode2",
        "spark-master", "spark-worker",
        "zookeeper", "kafka",
        "mlflow", "airflow", "streamlit"
    ]
    for s in required_services:
        assert s in services, f"Required service missing: {s}"

    print("SUCCESS: All docker-compose.yml configuration assertions passed!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_docker_compose_config())
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
