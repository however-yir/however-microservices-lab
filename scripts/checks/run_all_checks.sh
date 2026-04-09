#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_VENV="${USE_VENV:-1}"
VENV_DIR="${ROOT_DIR}/.venv-checks"
PYTHON_CMD="${PYTHON_BIN}"

run_step() {
  local title="$1"
  shift
  echo ""
  echo "==> ${title}"
  "$@"
}

run_step "Java checks (adservice: test + pmdMain)" \
  bash -lc "cd '${ROOT_DIR}/src/adservice' && chmod +x gradlew && ./gradlew test pmdMain"

run_step "Node checks (currencyservice: npm ci + npm test)" \
  bash -lc "cd '${ROOT_DIR}/src/currencyservice' && npm ci && npm test"

run_step "Node checks (paymentservice: npm ci + npm test)" \
  bash -lc "cd '${ROOT_DIR}/src/paymentservice' && npm ci && npm test"

if [[ "${USE_VENV}" == "1" ]]; then
  run_step "Python venv bootstrap (.venv-checks)" \
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  PYTHON_CMD="${VENV_DIR}/bin/python"
fi

run_step "Python dependency install (shoppingassistantservice)" \
  bash -lc "cd '${ROOT_DIR}/src/shoppingassistantservice' && '${PYTHON_CMD}' -m pip install --upgrade pip && '${PYTHON_CMD}' -m pip install -r requirements.txt"

run_step "Python lint (ruff)" \
  bash -lc "cd '${ROOT_DIR}/src/shoppingassistantservice' && '${PYTHON_CMD}' -m ruff check ."

run_step "Python type check (mypy)" \
  bash -lc "cd '${ROOT_DIR}/src/shoppingassistantservice' && '${PYTHON_CMD}' -m mypy shoppingassistantservice.py"

run_step "Python tests (pytest)" \
  bash -lc "cd '${ROOT_DIR}/src/shoppingassistantservice' && '${PYTHON_CMD}' -m pytest"

echo ""
echo "All checks finished successfully."
