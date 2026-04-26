from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNTER = Counter(
    "shopping_assistant_requests_total",
    "Total shopping assistant requests",
    ["status", "provider", "backend"],
)
REQUEST_LATENCY = Histogram(
    "shopping_assistant_request_latency_seconds",
    "Latency of shopping assistant requests",
    ["provider", "backend"],
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5, 8, 13),
)
RETRIEVAL_QUERY_COUNTER = Counter(
    "shopping_assistant_retrieval_queries_total",
    "Total retrieval queries",
    ["backend"],
)
RETRIEVAL_HIT_COUNTER = Counter(
    "shopping_assistant_retrieval_hits_total",
    "Total retrieved documents",
    ["backend"],
)
RETRIEVAL_HIT_RATIO = Gauge(
    "shopping_assistant_retrieval_hit_ratio",
    "Hit ratio for retrieval backend",
    ["backend"],
)
JSON_RELEVANCE_SCORE = Histogram(
    "shopping_assistant_json_relevance_score",
    "Relevance score for JSON fallback retrieval",
    buckets=(0, 1, 2, 3, 4, 5, 8, 13),
)
RATE_LIMIT_REJECT_COUNTER = Counter(
    "shopping_assistant_rate_limit_rejected_total",
    "Rejected requests by in-memory rate limiter",
)
CIRCUIT_BREAKER_STATE = Gauge(
    "shopping_assistant_circuit_breaker_open",
    "Circuit breaker state, 1 means open",
)
