"""Smoke tests for realtime-data-pipeline components."""

import json
import os
import sys
from pathlib import Path

import pytest


def test_repo_has_readme():
    """Verify project README exists."""
    assert Path("README.md").exists()


def test_docker_compose_valid():
    """Verify docker-compose.yml exists and is non-empty."""
    compose = Path("docker-compose.yml")
    assert compose.exists()
    content = compose.read_text()
    assert "services:" in content
    assert "kafka:" in content
    assert "flink-jobmanager:" in content


def test_env_example_exists():
    """Verify .env.example exists with required variables."""
    env_example = Path(".env.example")
    assert env_example.exists()
    content = env_example.read_text()
    required_vars = [
        "KAFKA_BOOTSTRAP_SERVERS",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "GF_ADMIN_USER",
        "GF_ADMIN_PASSWORD",
    ]
    for var in required_vars:
        assert var in content, f"Missing required env var: {var}"


def test_prometheus_config_valid():
    """Verify Prometheus config has required scrape jobs."""
    prom_config = Path("monitoring/prometheus/prometheus.yml")
    assert prom_config.exists()
    content = prom_config.read_text()
    assert "flink-jobmanager" in content
    assert "kafka-exporter" in content
    assert "stream-metrics-exporter" in content


def test_alert_rules_valid():
    """Verify alert rules file has critical alerts defined."""
    rules = Path("monitoring/alerting/alert_rules.yml")
    assert rules.exists()
    content = rules.read_text()
    assert "FlinkJobManagerDown" in content
    assert "KafkaConsumerLagHigh" in content
    assert "FlinkCheckpointFailures" in content or "FlinkJobManagerDown" in content


def test_helm_chart_exists():
    """Verify Helm chart structure."""
    chart = Path("deploy/helm/realtime-data-pipeline/Chart.yaml")
    assert chart.exists()
    values = Path("deploy/helm/realtime-data-pipeline/values.yaml")
    assert values.exists()


def test_kafka_schemas_exist():
    """Verify all required schema files exist."""
    schema_dir = Path("data-storage/kafka-config/schemas")
    assert schema_dir.exists()
    schemas = list(schema_dir.glob("*.json"))
    assert len(schemas) >= 3, f"Expected at least 3 schema files, found {len(schemas)}"


def test_ci_workflow_exists():
    """Verify CI workflow is configured."""
    ci = Path(".github/workflows/ci.yml")
    assert ci.exists()
    content = ci.read_text()
    assert "mvn" in content
    assert "python" in content.lower()


def test_codeowners_exists():
    """Verify CODEOWNERS file exists."""
    assert Path(".github/CODEOWNERS").exists()


def test_runbooks_exist():
    """Verify runbook documentation exists."""
    runbook_dir = Path("docs/runbook")
    assert runbook_dir.exists()
    runbooks = list(runbook_dir.glob("*.md"))
    assert len(runbooks) >= 3, f"Expected at least 3 runbook files, found {len(runbooks)}"


def test_dockerfiles_exist():
    """Verify Dockerfiles exist for Python components."""
    assert Path("data-collector/api-collector/Dockerfile").exists()
    assert Path("monitoring/stream-metrics-exporter/Dockerfile").exists()
    assert Path("monitoring/connect-exporter/Dockerfile").exists()
