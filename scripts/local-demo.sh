#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.local-demo.yml"
STATE_DIR="${ROOT_DIR}/.codex_tmp/local-demo"
PID_FILE="${STATE_DIR}/shoppingassistant.pid"
LOG_FILE="${STATE_DIR}/shoppingassistant.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${LOCAL_DEMO_VENV_DIR:-${ROOT_DIR}/.venv-local-demo}"
ASSISTANT_PORT="${ASSISTANT_PORT:-18081}"
OLLAMA_PORT="${LOCAL_DEMO_OLLAMA_PORT:-11434}"
REDIS_PORT="${LOCAL_DEMO_REDIS_PORT:-6379}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:0.5b}"
ACTION="${1:-start}"

compose() {
  docker compose -f "${COMPOSE_FILE}" "$@"
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-60}"
  for _ in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for ${url}" >&2
  return 1
}

wait_for_redis() {
  local attempts="${1:-60}"
  for _ in $(seq 1 "${attempts}"); do
    if compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for Redis on port ${REDIS_PORT}" >&2
  return 1
}

assistant_is_running() {
  [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" >/dev/null 2>&1
}

start_assistant() {
  mkdir -p "${STATE_DIR}"
  if assistant_is_running; then
    echo "shoppingassistantservice already running on http://127.0.0.1:${ASSISTANT_PORT}"
    return 0
  fi

  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  fi

  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -r "${ROOT_DIR}/src/shoppingassistantservice/requirements.txt"

  (
    cd "${ROOT_DIR}/src/shoppingassistantservice"
    env \
      MODEL_PROVIDER=ollama \
      OLLAMA_BASE_URL="http://localhost:${OLLAMA_PORT}" \
      OLLAMA_ALLOWED_HOSTS="localhost,127.0.0.1" \
      OLLAMA_MODEL="${OLLAMA_MODEL}" \
      VECTORSTORE_BACKEND=json \
      PRODUCT_CATALOG_JSON="${ROOT_DIR}/src/shoppingassistantservice/products.local.json" \
      ENABLE_TRACING=0 \
      RATE_LIMIT_MAX_REQUESTS=1000 \
      PORT="${ASSISTANT_PORT}" \
      "${VENV_DIR}/bin/python" shoppingassistantservice.py
  ) >"${LOG_FILE}" 2>&1 &
  echo "$!" > "${PID_FILE}"
}

start_demo() {
  command -v docker >/dev/null 2>&1 || {
    echo "Docker is required for local-demo." >&2
    exit 1
  }
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required for local-demo." >&2
    exit 1
  }

  mkdir -p "${STATE_DIR}"
  compose up -d redis ollama
  wait_for_redis
  wait_for_http "http://127.0.0.1:${OLLAMA_PORT}/api/tags" 90

  if [[ "${LOCAL_DEMO_PULL_MODEL:-0}" == "1" ]]; then
    compose exec -T ollama ollama pull "${OLLAMA_MODEL}"
  fi

  start_assistant
  wait_for_http "http://127.0.0.1:${ASSISTANT_PORT}/healthz" 60

  echo "Local demo is ready."
  echo "- Redis: 127.0.0.1:${REDIS_PORT}"
  echo "- Ollama: http://127.0.0.1:${OLLAMA_PORT}"
  echo "- shoppingassistantservice: http://127.0.0.1:${ASSISTANT_PORT}"
  echo "- Logs: ${LOG_FILE}"
  echo ""
  echo "To exercise the model path after pulling a model:"
  echo "  LOCAL_DEMO_PULL_MODEL=1 make local-demo"
  echo "  curl -sS -H 'Content-Type: application/json' -d '{\"message\":\"Recommend warm desk lighting\",\"image\":\"\"}' http://127.0.0.1:${ASSISTANT_PORT}/"
}

stop_demo() {
  if assistant_is_running; then
    kill "$(cat "${PID_FILE}")" >/dev/null 2>&1 || true
  fi
  rm -f "${PID_FILE}"
  compose down
  echo "Local demo stopped."
}

status_demo() {
  compose ps
  if assistant_is_running; then
    echo "shoppingassistantservice: running on http://127.0.0.1:${ASSISTANT_PORT}"
  else
    echo "shoppingassistantservice: stopped"
  fi
}

case "${ACTION}" in
  start)
    start_demo
    ;;
  stop)
    stop_demo
    ;;
  status)
    status_demo
    ;;
  *)
    echo "Usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
