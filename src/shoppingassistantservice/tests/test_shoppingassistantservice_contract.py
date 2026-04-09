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


def _make_app(monkeypatch: pytest.MonkeyPatch):
    json_catalog_path = str(Path(__file__).resolve().parent.parent / "products.local.json")
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "json")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)
    monkeypatch.setenv("ENABLE_TRACING", "0")
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐输出文本"),
    )
    return appmod.create_app(appmod._build_config())


def test_api_contract_success_shape(monkeypatch: pytest.MonkeyPatch):
    app = _make_app(monkeypatch)
    client = app.test_client()

    resp = client.post("/", json={"message": "modern minimalist room", "image": ""})
    assert resp.status_code == 200
    body = resp.get_json()
    assert isinstance(body, dict)
    assert "content" in body
    assert isinstance(body["content"], str)
    assert "trace_id" in body
    assert isinstance(body["trace_id"], str)


def test_api_contract_error_shape(monkeypatch: pytest.MonkeyPatch):
    app = _make_app(monkeypatch)
    client = app.test_client()

    resp = client.post("/", json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert isinstance(body, dict)
    assert body["error"] == "invalid request"
    assert isinstance(body["details"], list)


def test_health_and_probe_contract(monkeypatch: pytest.MonkeyPatch):
    app = _make_app(monkeypatch)
    client = app.test_client()

    health = client.get("/healthz")
    ready = client.get("/readyz")
    live = client.get("/livez")

    assert health.status_code == 200
    assert ready.status_code in (200, 503)
    assert live.status_code == 200
    assert "status" in health.get_json()
    assert "ready" in ready.get_json()
    assert live.get_json()["alive"] is True
