#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

required_containers=(
  rdp-kafka
  rdp-kafka-connect
  rdp-schema-registry
  rdp-postgres
  rdp-qdrant
  rdp-prometheus
  rdp-grafana
  rdp-stream-metrics-exporter
  rdp-connect-monitor-exporter
)

echo "[1/6] Checking required containers are running..."
for name in "${required_containers[@]}"; do
  if ! docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
    echo "[FAIL] Container not running: ${name}"
    exit 1
  fi
done

echo "[2/6] Checking HTTP endpoints..."
check_http() {
  local url=$1
  local label=$2
  if ! curl -fsS "$url" >/dev/null; then
    echo "[FAIL] ${label} endpoint failed: ${url}"
    exit 1
  fi
}

check_http "http://localhost:8083/" "Kafka Connect"
check_http "http://localhost:8086/subjects" "Schema Registry"
check_http "http://localhost:6333/healthz" "Qdrant"
check_http "http://localhost:9090/-/healthy" "Prometheus"
check_http "http://localhost:3000/api/health" "Grafana"
check_http "http://localhost:9108/metrics" "Stream Metrics Exporter"
check_http "http://localhost:9310/metrics" "Connect Monitor Exporter"

echo "[3/6] Checking Debezium connector registration..."
connectors_json=$(curl -fsS http://localhost:8083/connectors)
if ! echo "$connectors_json" | grep -q 'postgres-cdc-user-profile'; then
  echo "[FAIL] Debezium connector postgres-cdc-user-profile not found"
  echo "Current connectors: $connectors_json"
  exit 1
fi

echo "[4/6] Checking Qdrant collection exists..."
collections_json=$(curl -fsS http://localhost:6333/collections)
if ! echo "$collections_json" | grep -q 'rag_documents'; then
  echo "[FAIL] Qdrant collection rag_documents not found"
  echo "$collections_json"
  exit 1
fi

echo "[5/6] Checking Kafka topics..."
if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^rag_processed_chunks$'; then
  echo "[FAIL] Kafka topic rag_processed_chunks missing"
  exit 1
fi

if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^cdc.public.user_profile$'; then
  echo "[FAIL] Kafka topic cdc.public.user_profile missing"
  exit 1
fi

if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^realtime_stats_metrics$'; then
  echo "[FAIL] Kafka topic realtime_stats_metrics missing"
  exit 1
fi

if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^anomaly_alerts$'; then
  echo "[FAIL] Kafka topic anomaly_alerts missing"
  exit 1
fi

echo "[6/6] Checking new DLQ topics..."
if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^dlq_anomaly_detect$'; then
  echo "[FAIL] Kafka topic dlq_anomaly_detect missing"
  exit 1
fi

if ! docker exec rdp-kafka kafka-topics --bootstrap-server kafka:29092 --list | grep -q '^dlq_data_enrich$'; then
  echo "[FAIL] Kafka topic dlq_data_enrich missing"
  exit 1
fi

echo "[PASS] Smoke check passed."
