#!/usr/bin/env python3
"""Register JSON schemas to Schema Registry from local schema files."""

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
SCHEMA_DIR = pathlib.Path(os.getenv("SCHEMA_DIR", "/app/schemas"))
MAX_WAIT_SECONDS = int(os.getenv("SCHEMA_REGISTRY_WAIT_SECONDS", "120"))


def wait_schema_registry() -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    url = f"{SCHEMA_REGISTRY_URL}/subjects"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"schema registry not ready: {SCHEMA_REGISTRY_URL}")


def register_schema(subject: str, schema_text: str) -> None:
    url = f"{SCHEMA_REGISTRY_URL}/subjects/{subject}/versions"
    payload = {
        "schemaType": "JSON",
        "schema": schema_text,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        schema_id = body.get("id")
        print(f"[OK] subject={subject} id={schema_id}")


def set_compatibility(subject: str, level: str = "BACKWARD") -> None:
    url = f"{SCHEMA_REGISTRY_URL}/config/{subject}"
    payload = {"compatibility": level}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] subject={subject} compatibility={body.get('compatibility', level)}")
    except Exception as e:
        print(f"[WARN] Failed to set compatibility for {subject}: {e}")


def main() -> None:
    wait_schema_registry()

    if not SCHEMA_DIR.exists():
        raise FileNotFoundError(f"schema dir not found: {SCHEMA_DIR}")

    files = sorted(SCHEMA_DIR.glob("*.json"))
    if not files:
        raise RuntimeError(f"no schema files found in {SCHEMA_DIR}")

    for schema_file in files:
        subject = schema_file.stem
        schema_text = schema_file.read_text(encoding="utf-8")
        register_schema(subject, schema_text)

    for schema_file in files:
        subject = schema_file.stem
        set_compatibility(subject, "BACKWARD")


if __name__ == "__main__":
    main()
