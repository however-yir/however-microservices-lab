from pathlib import Path

import pytest

import shoppingassistantservice as appmod


class _DummyResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"response": self._content}


@pytest.fixture
def json_catalog_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "products.local.json")


def _build_test_config(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str, rate_limit_max_requests: int = 120
):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "json")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", str(rate_limit_max_requests))
    monkeypatch.setenv("MAX_RETRIES", "1")
    monkeypatch.setenv("ENABLE_TRACING", "0")
    return appmod._build_config()


def test_request_validation_rejects_empty_message(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐文本 [2ZYFJ3GM2N]"),
    )
    app = appmod.create_app(_build_test_config(monkeypatch, json_catalog_path))
    client = app.test_client()

    resp = client.post("/", json={"message": "", "image": ""})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "invalid request"


def test_rate_limit_blocks_second_request(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐文本 [2ZYFJ3GM2N]"),
    )
    app = appmod.create_app(
        _build_test_config(monkeypatch, json_catalog_path, rate_limit_max_requests=1)
    )
    client = app.test_client()

    ok_resp = client.post("/", json={"message": "kitchen style", "image": ""})
    assert ok_resp.status_code == 200
    limited_resp = client.post("/", json={"message": "kitchen style", "image": ""})
    assert limited_resp.status_code == 429


def test_metrics_endpoint_exposes_prometheus_metrics(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐文本 [2ZYFJ3GM2N]"),
    )
    app = appmod.create_app(_build_test_config(monkeypatch, json_catalog_path))
    client = app.test_client()

    client.post("/", json={"message": "scandinavian wood table", "image": ""})
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    text = metrics_resp.get_data(as_text=True)
    assert "shopping_assistant_requests_total" in text
    assert "shopping_assistant_retrieval_queries_total" in text
