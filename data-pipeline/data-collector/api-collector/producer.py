#!/usr/bin/env python3
"""Simulate user behavior events and publish to Kafka."""

import json
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from kafka import KafkaProducer

load_dotenv()

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
BASE_TOPIC = os.getenv("KAFKA_TOPIC", "user_behavior_events")
TOPIC_NAMESPACE = os.getenv("TOPIC_NAMESPACE", "").strip()
DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "tenant_demo")
TOPIC = f"{TOPIC_NAMESPACE}.{BASE_TOPIC}" if TOPIC_NAMESPACE else BASE_TOPIC
SLEEP_SECONDS = float(os.getenv("PRODUCER_SLEEP_SECONDS", "0.5"))

EVENT_TYPES = ["view", "click", "add_to_cart", "purchase"]
CHANNELS = ["app", "web", "mini_program"]


def random_event() -> dict:
    event_type = random.choices(EVENT_TYPES, weights=[60, 25, 10, 5], k=1)[0]
    risk_score = round(random.uniform(0.0, 1.0), 4)
    is_anomaly = risk_score >= 0.95 or (
        event_type == "purchase" and random.random() < 0.03
    )
    return {
        "event_id": str(uuid4()),
        "user_id": f"user_{random.randint(1, 5000)}",
        "event_type": event_type,
        "product_id": f"sku_{random.randint(1, 300)}",
        "price": round(random.uniform(19.9, 3999), 2) if event_type == "purchase" else 0,
        "channel": random.choice(CHANNELS),
        "event_time": datetime.now(timezone.utc).isoformat(),
        "risk_score": risk_score,
        "is_anomaly": is_anomaly,
        "tenant_id": DEFAULT_TENANT_ID,
        "schema_version": "v1",
    }


def main() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        linger_ms=50,
        batch_size=65536,
        buffer_memory=67108864,
        compression_type="lz4",
        acks="all",
        retries=3,
        max_in_flight_requests_per_connection=5,
    )

    print(f"[START] Producing to {TOPIC} @ {BOOTSTRAP_SERVERS}")
    try:
        while True:
            event = random_event()
            producer.send(TOPIC, event)
            print(json.dumps(event, ensure_ascii=False))
            time.sleep(SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\n[STOP] Producer interrupted by user")
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()
