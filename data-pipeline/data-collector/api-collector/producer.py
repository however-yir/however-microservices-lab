#!/usr/bin/env python3
"""Simulate user behavior events and publish to Kafka."""

import json
import os
import random
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
COLLECTOR_MODE = os.getenv("COLLECTOR_MODE", "producer").strip().lower()
HTTP_HOST = os.getenv("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8088"))

EVENT_TYPES = ["product_viewed", "assistant_recommended", "add_to_cart", "checkout_completed"]
CHANNELS = ["app", "web", "mini_program"]


def random_event() -> dict:
    event_type = random.choices(EVENT_TYPES, weights=[60, 25, 10, 5], k=1)[0]
    risk_score = round(random.uniform(0.0, 1.0), 4)
    is_anomaly = risk_score >= 0.95 or (
        event_type == "checkout_completed" and random.random() < 0.03
    )
    return {
        "event_id": str(uuid4()),
        "user_id": f"user_{random.randint(1, 5000)}",
        "event_type": event_type,
        "product_id": f"sku_{random.randint(1, 300)}",
        "price": round(random.uniform(19.9, 3999), 2)
        if event_type == "checkout_completed"
        else 0,
        "channel": random.choice(CHANNELS),
        "event_time": datetime.now(timezone.utc).isoformat(),
        "risk_score": risk_score,
        "is_anomaly": is_anomaly,
        "tenant_id": DEFAULT_TENANT_ID,
        "schema_version": "v1",
        "success": event_type != "checkout_completed" or random.random() > 0.08,
    }


def create_producer() -> KafkaProducer:
    return KafkaProducer(
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


def normalize_event(raw: dict) -> dict:
    event = dict(raw)
    event.setdefault("event_id", str(uuid4()))
    event.setdefault("user_id", "anonymous")
    event.setdefault("channel", "web")
    event.setdefault("tenant_id", DEFAULT_TENANT_ID)
    event.setdefault("schema_version", "v2")
    event.setdefault("event_time", datetime.now(timezone.utc).isoformat())
    if "event_type" not in event:
        raise ValueError("event_type is required")
    return event


class EventCollectorHandler(BaseHTTPRequestHandler):
    producer: KafkaProducer

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._write_json({"status": "ok", "topic": TOPIC})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/events":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            event = normalize_event(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as err:
            self._write_json({"error": str(err)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            # Wait on the send future: flush() alone swallows per-message
            # failures, and acking an event Kafka never accepted loses it.
            self.producer.send(TOPIC, event).get(timeout=5)
        except Exception as err:  # kafka-python raises KafkaError subclasses here.
            print(json.dumps({"kafka_error": str(err), "event": event}, ensure_ascii=False), flush=True)
            self._write_json({"error": f"kafka publish failed: {err}"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        print(json.dumps({"accepted": event}, ensure_ascii=False), flush=True)
        self._write_json({"status": "accepted", "topic": TOPIC}, HTTPStatus.ACCEPTED)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[HTTP] {self.address_string()} {fmt % args}", flush=True)

    def _write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_http_collector(producer: KafkaProducer) -> None:
    EventCollectorHandler.producer = producer
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), EventCollectorHandler)
    print(f"[START] HTTP collector on {HTTP_HOST}:{HTTP_PORT}, topic={TOPIC}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP] HTTP collector interrupted by user", flush=True)
    finally:
        server.server_close()


def run_random_producer(producer: KafkaProducer) -> None:
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


def main() -> None:
    producer = create_producer()
    try:
        if COLLECTOR_MODE == "http":
            run_http_collector(producer)
        else:
            run_random_producer(producer)
    finally:
        producer.close()


if __name__ == "__main__":
    main()
