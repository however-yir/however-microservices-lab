#!/usr/bin/env sh
set -eu

ES_URL="${ES_URL:-http://elasticsearch:9200}"
POLICY_FILE="${POLICY_FILE:-/config/ilm-policy-user-events.json}"
TEMPLATE_FILE="${TEMPLATE_FILE:-/config/user-events-index-template.json}"

until curl -s "${ES_URL}/_cluster/health" >/dev/null 2>&1; do
  echo "[WAIT] Elasticsearch is not ready yet..."
  sleep 2
done

curl -sS -X PUT "${ES_URL}/_ilm/policy/user-events-ilm-policy" \
  -H "Content-Type: application/json" \
  --data-binary @"${POLICY_FILE}" >/dev/null

echo "[OK] ILM policy user-events-ilm-policy applied"

curl -sS -X PUT "${ES_URL}/_index_template/user-events-template" \
  -H "Content-Type: application/json" \
  --data-binary @"${TEMPLATE_FILE}" >/dev/null

echo "[OK] index template user-events-template applied"

status=$(curl -s -o /dev/null -w '%{http_code}' "${ES_URL}/user-events-000001")
if [ "$status" = "404" ]; then
  curl -sS -X PUT "${ES_URL}/user-events-000001" \
    -H "Content-Type: application/json" \
    -d '{"aliases":{"user-events":{"is_write_index":true}}}' >/dev/null
  echo "[OK] bootstrap write index user-events-000001 created"
else
  echo "[OK] bootstrap write index already exists"
fi
