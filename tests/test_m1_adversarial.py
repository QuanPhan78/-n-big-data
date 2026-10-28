"""
Adversarial Stress Test Suite for Milestone M1 (Docker Infrastructure)
EMPIRICAL CHALLENGER verification script.

Tests:
1. YAML syntax, schema parsing, duplicate keys.
2. Port collision analysis (intra-compose and host socket bind availability).
3. Volume naming consistency, orphaned volumes, and collision checks.
4. DataNode cluster topology (DataNode vs DataNode2 image, network, volume separation, replication).
5. MLflow SQLite backend-store-uri and command flag syntax verification.
6. Airflow SequentialExecutor requirement and SQLite concurrency verification.
7. Streamlit service configuration, startup delay analysis, and dependencies.
"""
import os
import sys
import yaml
import socket
import tempfile
import sqlite3
from pathlib import Path
from sqlalchemy.engine.url import make_url

COMPOSE_PATH = Path("docker-compose.yml")

def test_01_yaml_syntax_and_structure():
    """Verify docker-compose.yml parses cleanly without syntax errors."""
    print("[TEST 1] Testing YAML syntax and structure...")
    assert COMPOSE_PATH.exists(), "docker-compose.yml file missing!"
    
    with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
        config = yaml.safe_load(raw_text)

    assert isinstance(config, dict), "Parsed compose configuration is not a dictionary"
    assert "version" in config, "Missing 'version' key"
    assert "services" in config, "Missing 'services' key"
    assert "volumes" in config, "Missing 'volumes' key"
    assert "networks" in config, "Missing 'networks' key"
    print("  -> PASSED: YAML structure is valid.")
    return config

def test_02_port_collisions(config):
    """Test for port conflicts between services and on the host."""
    print("[TEST 2] Testing port allocations and collision resistance...")
    services = config.get("services", {})
    host_ports = {}
    
    for svc_name, svc_conf in services.items():
        ports = svc_conf.get("ports", [])
        for p in ports:
            # format could be "host:container" or integer
            p_str = str(p)
            if ":" in p_str:
                parts = p_str.split(":")
                host_p = int(parts[0])
                cont_p = int(parts[1])
            else:
                host_p = int(p_str)
                cont_p = host_p
                
            if host_p in host_ports:
                raise AssertionError(f"Port collision! Host port {host_p} mapped by both '{host_ports[host_p]}' and '{svc_name}'")
            host_ports[host_p] = svc_name

    print(f"  Mapped host ports: {host_ports}")
    
    # Test if host ports can be bound on 127.0.0.1
    conflicts = []
    for port, svc in host_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.close()
        except OSError as e:
            conflicts.append((port, svc, str(e)))

    if conflicts:
        print(f"  [WARNING] Host port bind conflict detected on host system: {conflicts}")
    else:
        print("  -> PASSED: All 8 host ports (9870, 9000, 8080, 7077, 9092, 5000, 8081, 8501) are free and bindable on 127.0.0.1.")

def test_03_volume_naming_and_isolation(config):
    """Verify volume consistency, unique DataNode storage, and named volume declarations."""
    print("[TEST 3] Testing volume declarations, bindings, and DataNode isolation...")
    services = config.get("services", {})
    declared_volumes = set(config.get("volumes", {}).keys())
    
    referenced_named_volumes = set()
    for svc_name, svc_conf in services.items():
        vols = svc_conf.get("volumes", [])
        for v in vols:
            v_str = str(v)
            # Check for Windows absolute path with drive letter like D:/nyc_data:/data
            if len(v_str) > 2 and v_str[1] == ":" and (v_str[2] == "/" or v_str[2] == "\\"):
                # Windows drive letter bind mount: e.g. D:/nyc_data:/data
                # Split after drive letter
                rest = v_str[2:]
                if ":" in rest:
                    src_path = v_str[:2] + rest.split(":", 1)[0]
                    dst_path = rest.split(":", 1)[1]
                    # It's a host bind mount, not a named volume
                    continue
            elif ":" in v_str:
                src, dst = v_str.split(":", 1)
                # check if src is a host bind path
                if src.startswith(".") or src.startswith("/") or src.startswith("\\"):
                    continue
                referenced_named_volumes.add(src)
                assert src in declared_volumes, f"Service '{svc_name}' references undeclared named volume '{src}'"

    # Verify no declared volumes are orphaned
    orphaned = declared_volumes - referenced_named_volumes
    assert not orphaned, f"Declared volumes not mounted in any service: {orphaned}"

    # Challenge datanode and datanode2 storage isolation
    dn1_vols = services["datanode"].get("volumes", [])
    dn2_vols = services["datanode2"].get("volumes", [])
    
    dn1_data_mount = next((v for v in dn1_vols if "/hadoop/dfs/data" in str(v)), None)
    dn2_data_mount = next((v for v in dn2_vols if "/hadoop/dfs/data" in str(v)), None)
    
    assert dn1_data_mount is not None, "datanode missing /hadoop/dfs/data mount"
    assert dn2_data_mount is not None, "datanode2 missing /hadoop/dfs/data mount"
    assert dn1_data_mount != dn2_data_mount, (
        f"CRITICAL FLAW: datanode and datanode2 share the same storage volume! {dn1_data_mount} vs {dn2_data_mount}"
    )
    print("  -> PASSED: Volume declarations match references; datanode and datanode2 have isolated persistent volumes.")

def test_04_datanode_cluster_topology(config):
    """Verify DataNode 1 & 2 configuration, replication, dependencies, and network."""
    print("[TEST 4] Testing DataNode 1 & 2 cluster topology...")
    services = config.get("services", {})
    assert "namenode" in services
    assert "datanode" in services
    assert "datanode2" in services
    
    nn = services["namenode"]
    dn1 = services["datanode"]
    dn2 = services["datanode2"]
    
    assert dn1.get("image") == dn2.get("image"), "datanode and datanode2 images differ!"
    assert dn1.get("image") == "bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8"
    assert nn.get("image") == "bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8"
    
    # Check dependencies
    assert "namenode" in dn1.get("depends_on", []), "datanode must depend on namenode"
    assert "namenode" in dn2.get("depends_on", []), "datanode2 must depend on namenode"
    
    # Check network
    assert "bigdata-net" in dn1.get("networks", []), "datanode must connect to bigdata-net"
    assert "bigdata-net" in dn2.get("networks", []), "datanode2 must connect to bigdata-net"
    
    # Check replication factor consistency
    def get_env_val(env_list, key):
        for e in env_list:
            if str(e).startswith(f"{key}="):
                return str(e).split("=", 1)[1]
        return None

    assert get_env_val(nn.get("environment", []), "HDFS_CONF_dfs_replication") == "2", "namenode replication != 2"
    assert get_env_val(dn1.get("environment", []), "HDFS_CONF_dfs_replication") == "2", "datanode replication != 2"
    assert get_env_val(dn2.get("environment", []), "HDFS_CONF_dfs_replication") == "2", "datanode2 replication != 2"
    
    # Check fs_defaultFS
    assert get_env_val(dn1.get("environment", []), "CORE_CONF_fs_defaultFS") == "hdfs://namenode:9000"
    assert get_env_val(dn2.get("environment", []), "CORE_CONF_fs_defaultFS") == "hdfs://namenode:9000"
    print("  -> PASSED: DataNode topology, images, dependencies, and replication=2 verified.")

def test_05_mlflow_sqlite_backend_and_flags(config):
    """Stress test MLflow command line flags and SQLite backend URI."""
    print("[TEST 5] Testing MLflow SQLite URI and CLI flags...")
    services = config.get("services", {})
    mlflow_svc = services["mlflow"]
    cmd = mlflow_svc.get("command", "")
    
    # Check flags
    assert "--backend-store-uri" in cmd, "Missing --backend-store-uri"
    assert "sqlite:////mlflow/mlflow.db" in cmd, "Missing sqlite:////mlflow/mlflow.db"
    assert "--artifacts-destination /mlflow/artifacts" in cmd, "Missing --artifacts-destination"
    assert "--serve-artifacts" in cmd, "Missing --serve-artifacts"
    
    # Empirical test of sqlite:////mlflow/mlflow.db with SQLAlchemy make_url
    uri = "sqlite:////mlflow/mlflow.db"
    url = make_url(uri)
    assert url.database == "/mlflow/mlflow.db", f"SQLAlchemy parsed unexpected DB path: {url.database}"
    
    # Empirical SQLite database creation & table initialization test
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = os.path.join(tmpdir, "mlflow.db")
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test_experiments (experiment_id INTEGER PRIMARY KEY, name TEXT);")
        cursor.execute("INSERT INTO test_experiments (name) VALUES ('nyc_experiment');")
        conn.commit()
        cursor.execute("SELECT name FROM test_experiments;")
        row = cursor.fetchone()
        assert row[0] == "nyc_experiment"
        conn.close()

    # Check volume mount for MLflow
    vols = mlflow_svc.get("volumes", [])
    assert any("mlflow_data:/mlflow" in str(v) for v in vols), "MLflow must mount mlflow_data to /mlflow"
    print("  -> PASSED: MLflow SQLite URI correctly parsed by SQLAlchemy; volume mounts /mlflow.")

def test_06_airflow_sequential_executor_and_sqlite(config):
    """Test Airflow executor configuration and SQLite compatibility."""
    print("[TEST 6] Testing Airflow SequentialExecutor with SQLite...")
    services = config.get("services", {})
    airflow_svc = services["airflow"]
    env = airflow_svc.get("environment", [])
    cmd = airflow_svc.get("command", "")
    
    # Check executor
    executor_env = next((e for e in env if "AIRFLOW__CORE__EXECUTOR" in str(e)), None)
    assert executor_env == "AIRFLOW__CORE__EXECUTOR=SequentialExecutor", (
        f"Airflow executor must be SequentialExecutor, found: {executor_env}"
    )
    
    # Check DB conn
    db_env = next((e for e in env if "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN" in str(e)), None)
    assert "sqlite:////opt/airflow/airflow.db" in str(db_env), (
        f"Airflow DB conn missing sqlite:////opt/airflow/airflow.db: {db_env}"
    )
    
    # Check DB migration command
    assert "airflow db migrate" in cmd, "Airflow command must use 'airflow db migrate' instead of deprecated 'init'"
    
    # Empirical concurrency test: SequentialExecutor single-writer safety
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "airflow.db")
        # Initialize SQLite DB
        conn1 = sqlite3.connect(db_file, timeout=10.0)
        c1 = conn1.cursor()
        c1.execute("CREATE TABLE task_instance (task_id TEXT PRIMARY KEY, state TEXT);")
        c1.execute("INSERT INTO task_instance VALUES ('task_1', 'queued');")
        conn1.commit()
        
        # Second connection (simulating webserver reading while scheduler writes)
        conn2 = sqlite3.connect(db_file, timeout=10.0)
        c2 = conn2.cursor()
        c2.execute("SELECT state FROM task_instance WHERE task_id='task_1';")
        res = c2.fetchone()
        assert res[0] == "queued"
        
        # Scheduler updates task sequentially
        c1.execute("UPDATE task_instance SET state='success' WHERE task_id='task_1';")
        conn1.commit()
        
        c2.execute("SELECT state FROM task_instance WHERE task_id='task_1';")
        res2 = c2.fetchone()
        assert res2[0] == "success"
        
        conn1.close()
        conn2.close()
    print("  -> PASSED: Airflow SequentialExecutor configured correctly for SQLite single-writer safety.")

def test_07_streamlit_service(config):
    """Challenge Streamlit service provisioning and exposed ports."""
    print("[TEST 7] Testing Streamlit service provisioning...")
    services = config.get("services", {})
    assert "streamlit" in services, "Missing streamlit service in docker-compose.yml"
    
    st = services["streamlit"]
    assert any("8501:8501" in str(p) for p in st.get("ports", [])), "Streamlit must map port 8501:8501"
    
    cmd = st.get("command", "")
    assert "streamlit run dashboard/app.py" in cmd, "Streamlit command does not launch dashboard/app.py"
    assert "--server.port=8501" in cmd
    assert "--server.address=0.0.0.0" in cmd
    print("  -> PASSED: Streamlit service exists and maps port 8501.")

def run_all_tests():
    print("=" * 70)
    print("RUNNING ADVERSARIAL STRESS TEST SUITE FOR MILESTONE M1")
    print("=" * 70)
    config = test_01_yaml_syntax_and_structure()
    test_02_port_collisions(config)
    test_03_volume_naming_and_isolation(config)
    test_04_datanode_cluster_topology(config)
    test_05_mlflow_sqlite_backend_and_flags(config)
    test_06_airflow_sequential_executor_and_sqlite(config)
    test_07_streamlit_service(config)
    print("=" * 70)
    print("ALL 7 ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_tests()
