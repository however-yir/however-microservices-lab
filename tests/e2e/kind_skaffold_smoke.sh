#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-however-microservices-lab-e2e}"
NAMESPACE="${NAMESPACE:-however-e2e}"
FRONTEND_PORT="${FRONTEND_PORT:-18080}"
COOKIE_JAR="$(mktemp)"
PORT_FORWARD_PID=""

cleanup() {
  if [[ -n "${PORT_FORWARD_PID}" ]]; then
    kill "${PORT_FORWARD_PID}" >/dev/null 2>&1 || true
  fi
  rm -f "${COOKIE_JAR}"
}
trap cleanup EXIT

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
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

require_command kind
require_command kubectl
require_command skaffold
require_command curl

cd "${ROOT_DIR}"

if ! kind get clusters | grep -qx "${CLUSTER_NAME}"; then
  kind create cluster --name "${CLUSTER_NAME}"
fi

kubectl config use-context "kind-${CLUSTER_NAME}"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

skaffold run -p e2e --namespace "${NAMESPACE}"

kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/frontend
kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/cartservice
kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/checkoutservice
kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/productcatalogservice
kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/shoppingassistantservice
kubectl -n "${NAMESPACE}" wait --for=condition=available --timeout=600s deployment/ollama

kubectl -n "${NAMESPACE}" port-forward svc/frontend "${FRONTEND_PORT}:80" >/tmp/however-frontend-port-forward.log 2>&1 &
PORT_FORWARD_PID="$!"
wait_for_http "http://127.0.0.1:${FRONTEND_PORT}/_healthz"

curl -fsS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "http://127.0.0.1:${FRONTEND_PORT}/" >/tmp/however-e2e-home.html
curl -fsS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "http://127.0.0.1:${FRONTEND_PORT}/product/2ZYFJ3GM2N" >/tmp/however-e2e-product.html

curl -fsS -L -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" \
  -X POST "http://127.0.0.1:${FRONTEND_PORT}/cart" \
  -d "product_id=2ZYFJ3GM2N" \
  -d "quantity=1" >/tmp/however-e2e-cart-add.html

curl -fsS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" "http://127.0.0.1:${FRONTEND_PORT}/cart" >/tmp/however-e2e-cart.html

curl -fsS -L -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" \
  -X POST "http://127.0.0.1:${FRONTEND_PORT}/cart/checkout" \
  -d "email=e2e@example.com" \
  -d "street_address=1 Test Way" \
  -d "zip_code=94043" \
  -d "city=Mountain View" \
  -d "state=CA" \
  -d "country=United States" \
  -d "credit_card_number=4111111111111111" \
  -d "credit_card_expiration_month=12" \
  -d "credit_card_expiration_year=2035" \
  -d "credit_card_cvv=123" >/tmp/however-e2e-order.html

assistant_response="$(curl -fsS -c "${COOKIE_JAR}" -b "${COOKIE_JAR}" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:${FRONTEND_PORT}/bot" \
  -d '{"message":"Recommend warm lighting for a small room","image":""}')"

echo "${assistant_response}" | grep -q '"message"'
echo "${assistant_response}" | grep -q '"trace_id"'
echo "E2E smoke test passed for namespace ${NAMESPACE} on kind cluster ${CLUSTER_NAME}."
