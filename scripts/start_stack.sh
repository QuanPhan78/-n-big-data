#!/usr/bin/env bash
# Infrastructure startup script for NYC Ride-Hailing Big Data Pipeline (Milestone M1).
set -euo pipefail

echo "============================================================"
echo "  NYC Ride-Hailing Big Data Pipeline - Infrastructure Init  "
echo "============================================================"

if ! command -v docker >/dev/null 2>&1; then
    echo "[ERROR] docker command not found."
    exit 1
fi

echo "[INFO] Validating docker-compose.yml configuration..."
python3 scripts/verify_docker_compose.py || true

echo "[INFO] Starting all services with docker compose up -d..."
docker compose up -d || docker-compose up -d

echo "[INFO] Checking container status..."
sleep 3
docker ps

echo "============================================================"
echo "Service Endpoints:"
echo "  - NameNode Web UI:     http://localhost:9870"
echo "  - Spark Master UI:     http://localhost:8080"
echo "  - MLflow Server UI:    http://localhost:5000"
echo "  - Airflow Web UI:      http://localhost:8081"
echo "  - Streamlit Dashboard: http://localhost:8501"
echo "============================================================"
