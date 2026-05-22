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


class _FailingResponse:
    def raise_for_status(self):
        raise RuntimeError("model backend unavailable")

    def json(self):
        return {}


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


def test_response_includes_recommendation_explanations(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐文本 [2ZYFJ3GM2N]"),
    )
    app = appmod.create_app(_build_test_config(monkeypatch, json_catalog_path))
    client = app.test_client()

    resp = client.post("/", json={"message": "warm desk lamp", "image": ""})
    body = resp.get_json()

    assert resp.status_code == 200
    assert body["details"]["recommendations"]
    first = body["details"]["recommendations"][0]
    assert first["product_id"] == "2ZYFJ3GM2N"
    assert "reason" in first
    assert "source" in first
    assert first["confidence"] > 0


def test_ollama_provider_uses_configured_generate_endpoint(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _DummyResponse("推荐文本 [2ZYFJ3GM2N]")

    monkeypatch.setattr(appmod.requests, "post", fake_post)
    app = appmod.create_app(_build_test_config(monkeypatch, json_catalog_path))
    client = app.test_client()

    resp = client.post("/", json={"message": "warm desk lamp", "image": ""})
    assert resp.status_code == 200
    assert calls
    assert calls[0]["url"] == "http://localhost:11434/api/generate"
    assert calls[0]["json"]["model"] == "qwen2.5:7b"
    assert calls[0]["timeout"] == 60


def test_gemini_provider_contract_with_fake_client(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    class _FakeGeminiClient:
        def __init__(self, config, circuit_breaker):
            assert config.model_provider == "gemini"
            self._circuit_breaker = circuit_breaker

        def describe_room(self, image_url: str) -> str:
            assert image_url == ""
            return "gemini described a warm minimalist room"

        def recommend_products(
            self, room_description: str, relevant_docs: str, customer_prompt: str
        ) -> str:
            assert "gemini described" in room_description
            assert "warm minimalist" in customer_prompt
            assert isinstance(relevant_docs, str)
            return "Gemini 推荐 [2ZYFJ3GM2N]"

    monkeypatch.setenv("MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "json")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)
    monkeypatch.setenv("ENABLE_TRACING", "0")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "120")
    monkeypatch.setattr(appmod, "DesignModelClient", _FakeGeminiClient)

    app = appmod.create_app(appmod._build_config())
    resp = app.test_client().post(
        "/", json={"message": "warm minimalist desk setup", "image": ""}
    )

    assert resp.status_code == 200
    assert "Gemini 推荐" in resp.get_json()["content"]


def test_alloydb_backend_falls_back_to_json_catalog(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    for name in (
        "PROJECT_ID",
        "REGION",
        "ALLOYDB_DATABASE_NAME",
        "ALLOYDB_TABLE_NAME",
        "ALLOYDB_CLUSTER_NAME",
        "ALLOYDB_INSTANCE_NAME",
        "ALLOYDB_SECRET_NAME",
        "ALLOYDB_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "alloydb")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)
    monkeypatch.setenv("ENABLE_TRACING", "0")
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("推荐文本 [2ZYFJ3GM2N]"),
    )

    app = appmod.create_app(appmod._build_config())
    health = app.test_client().get("/healthz")

    assert health.status_code == 200
    assert health.get_json()["vectorstore_backend"] == "json"


def test_model_recommendation_failure_returns_degraded_response(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _DummyResponse("warm wood and neutral textiles")
        return _FailingResponse()

    monkeypatch.setenv("MAX_RETRIES", "0")
    monkeypatch.setattr(appmod.requests, "post", fake_post)
    app = appmod.create_app(_build_test_config(monkeypatch, json_catalog_path))
    client = app.test_client()

    resp = client.post("/", json={"message": "warm reading corner", "image": ""})
    body = resp.get_json()

    assert resp.status_code == 200
    assert "保护模式" in body["content"]
    assert "[NO_MATCH]" in body["content"]


def test_config_rejects_unknown_model_provider(
    monkeypatch: pytest.MonkeyPatch, json_catalog_path: str
):
    monkeypatch.setenv("MODEL_PROVIDER", "unknown")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "json")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)

    with pytest.raises(ValueError, match="MODEL_PROVIDER"):
        appmod._build_config()
