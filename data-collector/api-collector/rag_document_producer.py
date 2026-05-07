#!/usr/bin/env python3
"""Publish sample RAG documents to Kafka topic rag_raw_documents."""

import json
import os
import pathlib
from datetime import datetime, timezone
from uuid import uuid4

from kafka import KafkaProducer

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
BASE_TOPIC = os.getenv("RAG_TOPIC", "rag_raw_documents")
TOPIC_NAMESPACE = os.getenv("TOPIC_NAMESPACE", "").strip()
DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "tenant_demo")
TOPIC = f"{TOPIC_NAMESPACE}.{BASE_TOPIC}" if TOPIC_NAMESPACE else BASE_TOPIC
SAMPLE_FILE = pathlib.Path(__file__).parent / "samples" / "rag_documents.jsonl"


def load_samples():
    if SAMPLE_FILE.exists():
        records = []
        for line in SAMPLE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
        if records:
            return records

    return [
        {
            "doc_id": "campus-recruitment-001",
            "source": "campus-recruitment",
            "content": "校园招聘系统中，学生用户需要按岗位标签和企业信誉进行筛选，推荐系统需要结合点击、收藏、投递行为做实时反馈。",
            "metadata": {"lang": "zh", "domain": "recruitment"},
        },
        {
            "doc_id": "rag-agent-knowledge-001",
            "source": "rag-agent-starter",
            "content": "RAG pipeline requires document cleaning, semantic chunking, embedding generation, and vector database indexing with metadata filters.",
            "metadata": {"lang": "en", "domain": "rag"},
        },
    ]


def normalize(record):
    out = dict(record)
    out.setdefault("doc_id", str(uuid4()))
    out.setdefault("source", "unknown")
    out.setdefault("metadata", {})
    out.setdefault("event_time", datetime.now(timezone.utc).isoformat())
    out.setdefault("schema_version", "v1")
    out.setdefault("tenant_id", DEFAULT_TENANT_ID)
    if "content" not in out and "text" in out:
        out["content"] = out["text"]
    return out


def main() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        acks="all",
        linger_ms=50,
    )

    records = [normalize(item) for item in load_samples()]
    print(f"[START] publishing {len(records)} docs to topic={TOPIC} bootstrap={BOOTSTRAP_SERVERS}")

    for record in records:
        producer.send(TOPIC, record)
        print(json.dumps(record, ensure_ascii=False))

    producer.flush()
    producer.close()
    print("[DONE] RAG documents published")


if __name__ == "__main__":
    main()
