#!/usr/bin/env python3
"""Kafka Connect status exporter for Prometheus."""

import logging
import os
import signal
import sys
import time

import requests
from prometheus_client import Counter, Gauge, start_http_server

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    stream=sys.stdout,
)
logger = logging.getLogger("rdp.connect-exporter")

CONNECT_URL = os.getenv("KAFKA_CONNECT_URL", "http://kafka-connect:8083")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9310"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))

CONNECT_UP = Gauge("rdp_connect_up", "Whether Kafka Connect API is reachable")
CONNECTORS_TOTAL = Gauge("rdp_connect_connectors_total", "Number of discovered Kafka connectors")
CONNECTOR_STATUS = Gauge(
    "rdp_connect_connector_status",
    "Connector health status (1 means RUNNING, else 0)",
    ["connector"],
)
TASK_STATUS = Gauge(
    "rdp_connect_task_status",
    "Connector task status (1 means RUNNING, else 0)",
    ["connector", "task_id"],
)
TASK_FAILED_TOTAL = Counter(
    "rdp_connect_task_failed_total",
    "Task failures observed by polling transitions",
    ["connector", "task_id"],
)

_previous_task_state = {}
_running = True


def _shutdown(signum, frame):
    global _running
    logger.info("received signal %s, shutting down gracefully", signum)
    _running = False


def safe_get(path: str):
    response = requests.get(
        f"{CONNECT_URL}{path}",
        timeout=TIMEOUT_SECONDS,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def update_metrics():
    global _previous_task_state

    payload = safe_get("/connectors?expand=status")
    if not isinstance(payload, dict):
        payload = {}

    CONNECT_UP.set(1)
    CONNECTORS_TOTAL.set(len(payload))

    for connector_name, details in payload.items():
        status = details.get("status", {}) if isinstance(details, dict) else {}
        connector_state = str(status.get("connector", {}).get("state", "UNKNOWN")).upper()
        CONNECTOR_STATUS.labels(connector=connector_name).set(1 if connector_state == "RUNNING" else 0)

        tasks = status.get("tasks", []) if isinstance(status.get("tasks", []), list) else []
        for task in tasks:
            task_id = str(task.get("id", -1))
            task_state = str(task.get("state", "UNKNOWN")).upper()

            TASK_STATUS.labels(connector=connector_name, task_id=task_id).set(1 if task_state == "RUNNING" else 0)

            key = (connector_name, task_id)
            prev_state = _previous_task_state.get(key)
            if task_state == "FAILED" and prev_state != "FAILED":
                TASK_FAILED_TOTAL.labels(connector=connector_name, task_id=task_id).inc()
            _previous_task_state[key] = task_state


def main():
    start_http_server(METRICS_PORT)
    logger.info(
        "starting Kafka Connect exporter on port %d, connect_url=%s",
        METRICS_PORT,
        CONNECT_URL,
    )

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while _running:
        try:
            update_metrics()
        except Exception as ex:
            CONNECT_UP.set(0)
            logger.warning("failed to scrape Kafka Connect: %s", ex)
        time.sleep(POLL_INTERVAL_SECONDS)

    logger.info("connect exporter stopped")


if __name__ == "__main__":
    main()
