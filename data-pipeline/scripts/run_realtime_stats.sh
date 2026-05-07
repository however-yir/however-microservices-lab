#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOB_DIR="$ROOT_DIR/stream-processing/flink-jobs/realtime-stats"
FLINK_JOBMANAGER_CONTAINER="${FLINK_JOBMANAGER_CONTAINER:-rdp-flink-jobmanager}"

echo "[INFO] Building realtime-stats job..."
(
  cd "$JOB_DIR"
  mvn -DskipTests clean package
)

if ! docker ps --format '{{.Names}}' | grep -Fxq "$FLINK_JOBMANAGER_CONTAINER"; then
  echo "[ERROR] Flink JobManager container '$FLINK_JOBMANAGER_CONTAINER' is not running."
  echo "[HINT] Run: docker compose up -d"
  exit 1
fi

JAR_PATH="$(find "$JOB_DIR/target" -maxdepth 1 -type f -name 'realtime-stats-*.jar' ! -name 'original-*' | head -n 1)"
if [[ -z "${JAR_PATH}" ]]; then
  echo "[ERROR] Built jar not found under $JOB_DIR/target"
  exit 1
fi

JAR_FILE="$(basename "$JAR_PATH")"
echo "[INFO] Submitting job jar: $JAR_FILE"
docker exec "$FLINK_JOBMANAGER_CONTAINER" flink run "/opt/flink/usrlib/$JAR_FILE"
echo "[OK] realtime-stats submitted successfully."
