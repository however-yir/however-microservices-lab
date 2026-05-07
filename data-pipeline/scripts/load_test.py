#!/usr/bin/env python3
"""Simple load test for event throughput and latency baselines."""

import argparse
import json
import random
import statistics
import time
from datetime import datetime, timezone
from uuid import uuid4

from kafka import KafkaConsumer, KafkaProducer

EVENT_TYPES = ["view", "click", "add_to_cart", "purchase"]
CHANNELS = ["app", "web", "mini_program"]


def build_event(tenant_id: str) -> dict:
    event_type = random.choices(EVENT_TYPES, weights=[60, 25, 10, 5], k=1)[0]
    now = datetime.now(timezone.utc).isoformat()
    return {
        "event_id": str(uuid4()),
        "user_id": f"user_{random.randint(1, 200000)}",
        "event_type": event_type,
        "product_id": f"sku_{random.randint(1, 2000)}",
        "price": round(random.uniform(19.9, 2999), 2) if event_type == "purchase" else 0,
        "channel": random.choice(CHANNELS),
        "event_time": now,
        "tenant_id": tenant_id,
        "schema_version": "v1",
    }


def percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    k = int(round((len(values) - 1) * p))
    return values[k]


def run(args):
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        linger_ms=5,
        acks="all",
        retries=3,
    )

    ack_latencies = []
    sent = 0
    start = time.time()
    end = start + args.duration

    print(f"[START] load test topic={args.topic} bootstrap={args.bootstrap} rps={args.rps} duration={args.duration}s")

    while time.time() < end:
        loop_start = time.time()
        for _ in range(args.rps):
            tenant_id = f"tenant_{random.randint(1, args.tenants)}"
            event = build_event(tenant_id)
            t0 = time.time()
            future = producer.send(args.topic, event)
            future.get(timeout=10)
            ack_latencies.append((time.time() - t0) * 1000)
            sent += 1

        elapsed = time.time() - loop_start
        if elapsed < 1:
            time.sleep(1 - elapsed)

    producer.flush()
    duration = max(time.time() - start, 1e-9)
    throughput = sent / duration

    print("[RESULT] producer")
    print(f"  sent_total={sent}")
    print(f"  duration_seconds={duration:.2f}")
    print(f"  throughput_eps={throughput:.2f}")
    print(f"  ack_latency_ms_p50={percentile(ack_latencies, 0.50):.2f}")
    print(f"  ack_latency_ms_p95={percentile(ack_latencies, 0.95):.2f}")
    print(f"  ack_latency_ms_avg={statistics.mean(ack_latencies):.2f}" if ack_latencies else "  ack_latency_ms_avg=0")

    if args.metrics_topic:
        consumer = KafkaConsumer(
            args.metrics_topic,
            bootstrap_servers=args.bootstrap,
            auto_offset_reset="latest",
            enable_auto_commit=False,
            consumer_timeout_ms=args.metrics_wait * 1000,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

        metric_latencies = []
        now = time.time()
        for message in consumer:
            payload = message.value if isinstance(message.value, dict) else {}
            event_time = payload.get("event_time")
            if not event_time:
                continue
            try:
                ts = datetime.fromisoformat(event_time.replace("Z", "+00:00")).timestamp()
                metric_latencies.append(max(0.0, now - ts))
            except Exception:
                continue

        if metric_latencies:
            print("[RESULT] stream")
            print(f"  metrics_topic={args.metrics_topic}")
            print(f"  metric_latency_s_p50={percentile(metric_latencies, 0.50):.2f}")
            print(f"  metric_latency_s_p95={percentile(metric_latencies, 0.95):.2f}")
        else:
            print("[RESULT] stream")
            print("  no metric messages observed in wait window")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Realtime pipeline load test")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--topic", default="user_behavior_events")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--rps", type=int, default=200, help="Events per second")
    parser.add_argument("--tenants", type=int, default=3, help="Number of simulated tenants")
    parser.add_argument("--metrics-topic", default="realtime_stats_metrics")
    parser.add_argument("--metrics-wait", type=int, default=15, help="Seconds to wait for metrics topic sample")
    run(parser.parse_args())
