#!/usr/bin/env bash
set -euo pipefail

QDRANT_URL=${QDRANT_URL:-http://localhost:6333}
COLLECTION=${COLLECTION:-rag_documents}
VECTOR_SIZE=${VECTOR_SIZE:-128}
DISTANCE=${DISTANCE:-Cosine}

curl -sS -X PUT "${QDRANT_URL}/collections/${COLLECTION}" \
  -H "Content-Type: application/json" \
  -d "{
    \"vectors\": {
      \"size\": ${VECTOR_SIZE},
      \"distance\": \"${DISTANCE}\"
    }
  }" | jq .
