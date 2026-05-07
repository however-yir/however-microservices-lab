#!/usr/bin/env bash
set -euo pipefail

BROKER_CONTAINER=${BROKER_CONTAINER:-rdp-kafka}
TOPIC_NAMESPACE=${TOPIC_NAMESPACE:-}

if ! docker ps --format '{{.Names}}' | grep -q "^${BROKER_CONTAINER}$"; then
  echo "[ERROR] Kafka container '${BROKER_CONTAINER}' is not running."
  echo "Run: docker compose up -d kafka zookeeper"
  exit 1
fi

create_topic() {
  local topic=$1
  local partitions=$2
  local retention_ms=$3

  docker exec "${BROKER_CONTAINER}" kafka-topics \
    --bootstrap-server kafka:29092 \
    --create --if-not-exists \
    --topic "${topic}" \
    --partitions "${partitions}" \
    --replication-factor 1 \
    --config cleanup.policy=delete \
    --config retention.ms="${retention_ms}"
}

topic_name() {
  local raw_name=$1
  if [ -n "${TOPIC_NAMESPACE}" ]; then
    printf "%s.%s" "${TOPIC_NAMESPACE}" "${raw_name}"
  else
    printf "%s" "${raw_name}"
  fi
}

create_topic "$(topic_name user_behavior_events)" 6 604800000
create_topic "$(topic_name rag_raw_documents)" 3 1209600000
create_topic "$(topic_name rag_processed_chunks)" 3 1209600000
create_topic "$(topic_name cdc_user_profile)" 3 604800000
create_topic "$(topic_name app_logs)" 3 259200000
create_topic "$(topic_name cdc.public.user_profile)" 3 604800000
create_topic "$(topic_name realtime_stats_metrics)" 3 604800000
create_topic "$(topic_name dlq_realtime_stats)" 3 604800000
create_topic "$(topic_name anomaly_alerts)" 3 604800000
create_topic "$(topic_name dlq_anomaly_detect)" 3 604800000
create_topic "$(topic_name dlq_data_enrich)" 3 604800000

docker exec "${BROKER_CONTAINER}" kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --if-not-exists \
  --topic _connect_configs \
  --partitions 1 \
  --replication-factor 1 \
  --config cleanup.policy=compact

docker exec "${BROKER_CONTAINER}" kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --if-not-exists \
  --topic _connect_offsets \
  --partitions 25 \
  --replication-factor 1 \
  --config cleanup.policy=compact

docker exec "${BROKER_CONTAINER}" kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --if-not-exists \
  --topic _connect_statuses \
  --partitions 5 \
  --replication-factor 1 \
  --config cleanup.policy=compact

docker exec "${BROKER_CONTAINER}" kafka-topics \
  --bootstrap-server kafka:29092 \
  --create --if-not-exists \
  --topic schema-changes.cdc \
  --partitions 1 \
  --replication-factor 1 \
  --config cleanup.policy=compact

printf "\n[OK] Topics ready:\n"
docker exec "${BROKER_CONTAINER}" kafka-topics --bootstrap-server kafka:29092 --list | sort
