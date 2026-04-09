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


def test_frontend_payload_to_assistant_e2e(monkeypatch: pytest.MonkeyPatch):
    """
    E2E contract from frontend form payload to shoppingassistantservice response.
    Frontend sends message + image fields to '/' endpoint.
    """
    json_catalog_path = str(Path(__file__).resolve().parent.parent / "products.local.json")
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("VECTORSTORE_BACKEND", "json")
    monkeypatch.setenv("PRODUCT_CATALOG_JSON", json_catalog_path)
    monkeypatch.setenv("ENABLE_TRACING", "0")

    # The service calls ollama twice (describe + recommend); return valid output both times.
    monkeypatch.setattr(
        appmod.requests,
        "post",
        lambda *args, **kwargs: _DummyResponse("建议采用木色和浅灰色软装"),
    )

    app = appmod.create_app(appmod._build_config())
    client = app.test_client()

    # Simulate frontend encoded message
    payload = {
        "message": "minimal%20living%20room%20with%20warm%20lighting",
        "image": "",
    }
    resp = client.post("/", json=payload)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "content" in body
    assert "推荐ID:" in body["content"]
