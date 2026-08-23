#!/usr/bin/env python3
"""Export business + stream metrics from Kafka to Prometheus."""

import json
import logging
import os
import signal
import sys
import time
from collections import Counter, defaultdict, deque
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("rdp.metrics-exporter")

from kafka import KafkaConsumer
from prometheus_client import Counter as PromCounter
from prometheus_client import Gauge, Histogram, start_http_server

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_EVENT_TOPIC = os.getenv("KAFKA_EVENT_TOPIC", os.getenv("KAFKA_TOPIC", "user_behavior_events"))
KAFKA_METRIC_TOPIC = os.getenv("KAFKA_METRIC_TOPIC", "realtime_stats_metrics")
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "stream-metrics-exporter")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9108"))
UV_WINDOW_SECONDS = int(os.getenv("UV_WINDOW_SECONDS", "300"))
POLL_TIMEOUT_MS = int(os.getenv("POLL_TIMEOUT_MS", "1000"))

EVENTS_TOTAL = PromCounter(
    "rdp_events_total",
    "Total user behavior events",
    ["event_type", "channel", "tenant_id"],
)

EVENT_PARSE_FAILURES_TOTAL = PromCounter(
    "rdp_event_parse_failures_total",
    "Total malformed or unparsable event messages",
)

ANOMALY_EVENTS_TOTAL = PromCounter(
    "rdp_anomaly_events_total",
    "Total anomaly events observed in stream",
    ["tenant_id"],
)

UNIQUE_USERS_5M = Gauge(
    "rdp_unique_users_5m",
    "Approximate unique users in the last 5 minutes",
    ["tenant_id"],
)

CONVERSION_RATE = Gauge(
    "rdp_conversion_rate",
    "Checkout-to-product-view conversion rate in percent",
    ["tenant_id"],
)

RECOMMENDATION_CLICK_RATE = Gauge(
    "rdp_recommendation_click_rate",
    "Assistant recommendation click-through rate in percent",
    ["tenant_id"],
)

ADD_TO_CART_CONVERSION_RATE = Gauge(
    "rdp_add_to_cart_conversion_rate",
    "Add-to-cart conversion rate from product views in percent",
    ["tenant_id"],
)

CHECKOUT_SUCCESS_RATE = Gauge(
    "rdp_checkout_success_rate",
    "Checkout completion success rate in percent",
    ["tenant_id"],
)

ABNORMAL_SEQUENCES_TOTAL = PromCounter(
    "rdp_abnormal_sequences_total",
    "Total abnormal business event sequences",
    ["tenant_id", "sequence"],
)

FUNNEL_EVENTS_5M = Gauge(
    "rdp_funnel_events_5m",
    "Event funnel counts in rolling window",
    ["stage", "channel"],
)

CHANNEL_EVENTS_5M = Gauge(
    "rdp_channel_events_5m",
    "Channel-level event counts in rolling window",
    ["channel"],
)

PIPELINE_LATENCY_SECONDS = Histogram(
    "rdp_pipeline_latency_seconds",
    "Latency from event_time to exporter ingestion",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60, 120),
)

FLINK_WINDOW_METRIC = Gauge(
    "rdp_flink_window_metric",
    "Window metric values emitted by realtime-stats job",
    ["metric_name", "event_type", "tenant_id", "schema_version"],
)

FLINK_METRIC_MESSAGES_TOTAL = PromCounter(
    "rdp_flink_metric_messages_total",
    "Total metric messages consumed from realtime_stats_metrics topic",
    ["metric_name"],
)

_running = True


def _shutdown(signum, frame):
    global _running
    logger.info("received signal %s, shutting down gracefully", signum)
    _running = False


TENANT_VIEW_TOTAL = defaultdict(int)
TENANT_PURCHASE_TOTAL = defaultdict(int)
TENANT_ASSISTANT_RECOMMEND_TOTAL = defaultdict(int)
TENANT_RECOMMENDATION_CLICK_TOTAL = defaultdict(int)
TENANT_ADD_TO_CART_TOTAL = defaultdict(int)
TENANT_CHECKOUT_TOTAL = defaultdict(int)
TENANT_CHECKOUT_SUCCESS_TOTAL = defaultdict(int)
TENANT_USER_COUNTER = defaultdict(Counter)
ROLLING_EVENTS = deque()
CHANNEL_COUNTER = Counter()
FUNNEL_COUNTER = Counter()
TENANTS_SEEN = set()
CHANNELS_SEEN = set()
USER_STAGE_SEEN = defaultdict(set)
USER_STAGE_LAST_SEEN = defaultdict(float)
LAST_STAGE_GC_TS = 0.0


def parse_event_time(event):
    event_time = event.get("event_time")
    if not event_time:
        return time.time()

    try:
        if isinstance(event_time, (int, float)):
            return float(event_time)
        if event_time.endswith("Z"):
            event_time = event_time.replace("Z", "+00:00")
        return datetime.fromisoformat(event_time).timestamp()
    except (TypeError, ValueError):
        return time.time()


def is_anomaly(event):
    if event.get("is_anomaly") is True:
        return True
    risk_score = event.get("risk_score")
    try:
        return risk_score is not None and float(risk_score) >= 0.8
    except (TypeError, ValueError):
        return False


def normalize_event(raw):
    if not isinstance(raw, dict):
        return None

    event_type = str(raw.get("event_type", "unknown"))
    user_id = str(raw.get("user_id", "unknown"))
    tenant_id = str(raw.get("tenant_id", "default"))
    channel = str(raw.get("channel", "unknown"))
    event_ts = parse_event_time(raw)
    stage = normalize_funnel_stage(event_type)

    return {
        "event_type": event_type,
        "stage": stage,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "channel": channel,
        "event_ts": event_ts,
        "raw": raw,
    }


def normalize_funnel_stage(event_type):
    aliases = {
        "view": "product_viewed",
        "product_viewed": "product_viewed",
        "click": "assistant_recommended",
        "assistant_recommended": "assistant_recommended",
        "add_to_cart": "add_to_cart",
        "purchase": "checkout_completed",
        "checkout_completed": "checkout_completed",
    }
    return aliases.get(event_type, event_type)


def update_business_kpis(event):
    event_type = event["event_type"]
    stage = event["stage"]
    tenant_id = event["tenant_id"]
    raw = event["raw"]

    if stage == "product_viewed":
        TENANT_VIEW_TOTAL[tenant_id] += 1
        if raw.get("source") == "assistant":
            TENANT_RECOMMENDATION_CLICK_TOTAL[tenant_id] += 1
    elif stage == "assistant_recommended":
        TENANT_ASSISTANT_RECOMMEND_TOTAL[tenant_id] += max(
            1, len(raw.get("recommendation_ids") or [])
        )
    elif stage == "add_to_cart":
        TENANT_ADD_TO_CART_TOTAL[tenant_id] += 1
    elif stage == "checkout_completed":
        TENANT_PURCHASE_TOTAL[tenant_id] += 1
        TENANT_CHECKOUT_TOTAL[tenant_id] += 1
        if raw.get("success", True) is True:
            TENANT_CHECKOUT_SUCCESS_TOTAL[tenant_id] += 1

    views = TENANT_VIEW_TOTAL[tenant_id]
    purchases = TENANT_PURCHASE_TOTAL[tenant_id]
    value = (purchases / views) * 100.0 if views > 0 else 0.0
    CONVERSION_RATE.labels(tenant_id=tenant_id).set(value)

    recommendation_total = TENANT_ASSISTANT_RECOMMEND_TOTAL[tenant_id]
    recommendation_clicks = TENANT_RECOMMENDATION_CLICK_TOTAL[tenant_id]
    recommendation_rate = (
        (recommendation_clicks / recommendation_total) * 100.0
        if recommendation_total > 0
        else 0.0
    )
    RECOMMENDATION_CLICK_RATE.labels(tenant_id=tenant_id).set(recommendation_rate)

    add_to_cart_rate = (
        (TENANT_ADD_TO_CART_TOTAL[tenant_id] / views) * 100.0 if views > 0 else 0.0
    )
    ADD_TO_CART_CONVERSION_RATE.labels(tenant_id=tenant_id).set(add_to_cart_rate)

    checkout_total = TENANT_CHECKOUT_TOTAL[tenant_id]
    checkout_rate = (
        (TENANT_CHECKOUT_SUCCESS_TOTAL[tenant_id] / checkout_total) * 100.0
        if checkout_total > 0
        else 0.0
    )
    CHECKOUT_SUCCESS_RATE.labels(tenant_id=tenant_id).set(checkout_rate)


def update_sequence_state(event):
    key = (event["tenant_id"], event["user_id"])
    stages = USER_STAGE_SEEN[key]
    stage = event["stage"]

    if stage == "add_to_cart" and "product_viewed" not in stages:
        ABNORMAL_SEQUENCES_TOTAL.labels(
            tenant_id=event["tenant_id"], sequence="cart_without_view"
        ).inc()
    if stage == "checkout_completed" and "add_to_cart" not in stages:
        ABNORMAL_SEQUENCES_TOTAL.labels(
            tenant_id=event["tenant_id"], sequence="checkout_without_cart"
        ).inc()

    stages.add(stage)
    USER_STAGE_LAST_SEEN[key] = max(
        USER_STAGE_LAST_SEEN[key], event["event_ts"]
    )


def evict_stale_stage_state(now_ts):
    """Drop per-user sequence state not refreshed within the UV window.

    Keeps USER_STAGE_SEEN / USER_STAGE_LAST_SEEN bounded to recently active
    users instead of growing forever. Runs at most once per window.
    """
    global LAST_STAGE_GC_TS
    if now_ts - LAST_STAGE_GC_TS < UV_WINDOW_SECONDS:
        return
    LAST_STAGE_GC_TS = now_ts

    threshold = now_ts - UV_WINDOW_SECONDS
    stale_keys = [key for key, seen_ts in USER_STAGE_LAST_SEEN.items() if seen_ts < threshold]
    for key in stale_keys:
        del USER_STAGE_LAST_SEEN[key]
        USER_STAGE_SEEN.pop(key, None)


def evict_old_events(now_ts):
    threshold = now_ts - UV_WINDOW_SECONDS
    while ROLLING_EVENTS and ROLLING_EVENTS[0][0] < threshold:
        _, old_user, old_channel, old_stage, old_tenant = ROLLING_EVENTS.popleft()

        tenant_counter = TENANT_USER_COUNTER[old_tenant]
        tenant_counter[old_user] -= 1
        if tenant_counter[old_user] <= 0:
            del tenant_counter[old_user]

        CHANNEL_COUNTER[old_channel] -= 1
        if CHANNEL_COUNTER[old_channel] <= 0:
            del CHANNEL_COUNTER[old_channel]

        key = (old_channel, old_stage)
        FUNNEL_COUNTER[key] -= 1
        if FUNNEL_COUNTER[key] <= 0:
            del FUNNEL_COUNTER[key]


def publish_rolling_gauges():
    for tenant_id in TENANTS_SEEN:
        UNIQUE_USERS_5M.labels(tenant_id=tenant_id).set(len(TENANT_USER_COUNTER.get(tenant_id, {})))

    for channel in CHANNELS_SEEN:
        CHANNEL_EVENTS_5M.labels(channel=channel).set(CHANNEL_COUNTER.get(channel, 0))

    funnel_stages = [
        "product_viewed",
        "assistant_recommended",
        "add_to_cart",
        "checkout_completed",
    ]
    for channel in CHANNELS_SEEN:
        for stage in funnel_stages:
            FUNNEL_EVENTS_5M.labels(stage=stage, channel=channel).set(FUNNEL_COUNTER.get((channel, stage), 0))


def handle_business_event(payload):
    event = normalize_event(payload)
    if event is None:
        EVENT_PARSE_FAILURES_TOTAL.inc()
        return

    tenant_id = event["tenant_id"]
    channel = event["channel"]
    event_type = event["event_type"]
    event_ts = event["event_ts"]

    TENANTS_SEEN.add(tenant_id)
    CHANNELS_SEEN.add(channel)

    EVENTS_TOTAL.labels(event_type=event_type, channel=channel, tenant_id=tenant_id).inc()

    latency = max(0.0, time.time() - event_ts)
    PIPELINE_LATENCY_SECONDS.observe(latency)

    update_business_kpis(event)
    update_sequence_state(event)

    if is_anomaly(event["raw"]):
        ANOMALY_EVENTS_TOTAL.labels(tenant_id=tenant_id).inc()

    ROLLING_EVENTS.append((event_ts, event["user_id"], channel, event["stage"], tenant_id))
    TENANT_USER_COUNTER[tenant_id][event["user_id"]] += 1
    CHANNEL_COUNTER[channel] += 1
    FUNNEL_COUNTER[(channel, event["stage"])] += 1

    evict_old_events(event_ts)
    evict_stale_stage_state(event_ts)
    publish_rolling_gauges()


def handle_flink_metric(payload):
    if not isinstance(payload, dict):
        EVENT_PARSE_FAILURES_TOTAL.inc()
        return

    metric_name = str(payload.get("metric_name", "unknown"))
    event_type = str(payload.get("event_type", "all"))
    tenant_id = str(payload.get("tenant_id", "default"))
    schema_version = str(payload.get("schema_version", "v1"))

    try:
        value = float(payload.get("value", 0.0))
    except (TypeError, ValueError):
        EVENT_PARSE_FAILURES_TOTAL.inc()
        return

    FLINK_WINDOW_METRIC.labels(
        metric_name=metric_name,
        event_type=event_type,
        tenant_id=tenant_id,
        schema_version=schema_version,
    ).set(value)
    FLINK_METRIC_MESSAGES_TOTAL.labels(metric_name=metric_name).inc()


def deserialize_payload(raw):
    """Decode a Kafka message value into a parsed JSON payload.

    Malformed messages are counted and returned as None instead of raising,
    so a single poison message cannot kill the consume loop.
    """
    try:
        return json.loads(raw.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        EVENT_PARSE_FAILURES_TOTAL.inc()
        return None


def main():
    topics = sorted({KAFKA_EVENT_TOPIC, KAFKA_METRIC_TOPIC})
    start_http_server(METRICS_PORT)
    logger.info(
        "starting metrics exporter on port %d, topics=%s, bootstrap=%s",
        METRICS_PORT,
        topics,
        KAFKA_BOOTSTRAP_SERVERS,
    )

    consumer = KafkaConsumer(
        *topics,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda v: v,
    )

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while _running:
        records = consumer.poll(timeout_ms=POLL_TIMEOUT_MS)
        for topic_partition, messages in records.items():
            topic = topic_partition.topic
            for message in messages:
                payload = deserialize_payload(message.value)
                if payload is None:
                    continue
                try:
                    if topic == KAFKA_METRIC_TOPIC:
                        handle_flink_metric(payload)
                    else:
                        handle_business_event(payload)
                except Exception:
                    logger.exception(
                        "failed to handle message on topic %s (offset %s), skipping",
                        topic,
                        getattr(message, "offset", "unknown"),
                    )

    logger.info("shutting down consumer")
    consumer.close()
    logger.info("metrics exporter stopped")


if __name__ == "__main__":
    main()
