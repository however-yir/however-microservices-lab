#!/usr/bin/python
#
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast
from urllib.parse import unquote, urlparse

import requests
from flask import Flask, Response, g, request
from google.cloud import secretmanager_v1
from langchain_core.messages import HumanMessage
from langchain_google_alloydb_pg import AlloyDBEngine, AlloyDBVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field, ValidationError, field_validator

DEFAULT_PRODUCT_CATALOG = Path(__file__).resolve().parent / "products.local.json"
DEFAULT_PROMPT_DIR = Path(__file__).resolve().parent / "prompts" / "v1"
PRODUCT_ID_PATTERN = re.compile(r"\[([A-Za-z0-9_-]{3,64})\]")

REQUEST_COUNTER = Counter(
    "shopping_assistant_requests_total",
    "Total shopping assistant requests",
    ["status", "provider", "backend"],
)
REQUEST_LATENCY = Histogram(
    "shopping_assistant_request_latency_seconds",
    "Latency of shopping assistant requests",
    ["provider", "backend"],
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5, 8, 13),
)
RETRIEVAL_QUERY_COUNTER = Counter(
    "shopping_assistant_retrieval_queries_total",
    "Total retrieval queries",
    ["backend"],
)
RETRIEVAL_HIT_COUNTER = Counter(
    "shopping_assistant_retrieval_hits_total",
    "Total retrieved documents",
    ["backend"],
)
RETRIEVAL_HIT_RATIO = Gauge(
    "shopping_assistant_retrieval_hit_ratio",
    "Hit ratio for retrieval backend",
    ["backend"],
)
JSON_RELEVANCE_SCORE = Histogram(
    "shopping_assistant_json_relevance_score",
    "Relevance score for JSON fallback retrieval",
    buckets=(0, 1, 2, 3, 4, 5, 8, 13),
)
RATE_LIMIT_REJECT_COUNTER = Counter(
    "shopping_assistant_rate_limit_rejected_total",
    "Rejected requests by in-memory rate limiter",
)
CIRCUIT_BREAKER_STATE = Gauge(
    "shopping_assistant_circuit_breaker_open",
    "Circuit breaker state, 1 means open",
)


@dataclass(frozen=True)
class AppConfig:
    model_provider: str
    gemini_vision_model: str
    gemini_text_model: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    ollama_allowed_hosts: tuple[str, ...]
    vectorstore_backend: str
    vector_top_k: int
    product_catalog_json: str
    alloydb_project_id: str
    alloydb_region: str
    alloydb_database_name: str
    alloydb_table_name: str
    alloydb_cluster_name: str
    alloydb_instance_name: str
    alloydb_secret_name: str
    alloydb_user: str
    alloydb_password: str
    port: int
    max_retries: int
    retry_backoff_seconds: float
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: int
    rate_limit_window_seconds: int
    rate_limit_max_requests: int
    enable_tracing: bool
    otel_service_name: str
    otel_collector_endpoint: str


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    image: str = ""

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = unquote(value).strip()
        if not normalized:
            raise ValueError("message cannot be empty")
        return normalized


class RateLimiter:
    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.events: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            queue = self.events.setdefault(key, deque())
            while queue and now - queue[0] > self.window_seconds:
                queue.popleft()
            if len(queue) >= self.max_requests:
                return False
            queue.append(now)
            return True


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: int):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failure_count = 0
        self.open_until = 0.0
        self.lock = threading.Lock()

    def can_call(self) -> bool:
        with self.lock:
            if time.time() >= self.open_until:
                return True
            return False

    def mark_success(self) -> None:
        with self.lock:
            self.failure_count = 0
            self.open_until = 0.0
            CIRCUIT_BREAKER_STATE.set(0)

    def mark_failure(self) -> None:
        with self.lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.open_until = time.time() + self.reset_seconds
                CIRCUIT_BREAKER_STATE.set(1)


def _build_config() -> AppConfig:
    allowlist = tuple(
        h.strip() for h in os.getenv("OLLAMA_ALLOWED_HOSTS", "ollama,127.0.0.1,localhost").split(",") if h.strip()
    )
    return AppConfig(
        model_provider=os.getenv("MODEL_PROVIDER", "gemini").strip().lower(),
        gemini_vision_model=os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash"),
        gemini_text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-1.5-flash"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60")),
        ollama_allowed_hosts=allowlist,
        vectorstore_backend=os.getenv("VECTORSTORE_BACKEND", "alloydb").strip().lower(),
        vector_top_k=int(os.getenv("VECTOR_TOP_K", "6")),
        product_catalog_json=os.getenv("PRODUCT_CATALOG_JSON", str(DEFAULT_PRODUCT_CATALOG)),
        alloydb_project_id=os.getenv("PROJECT_ID", "").strip(),
        alloydb_region=os.getenv("REGION", "").strip(),
        alloydb_database_name=os.getenv("ALLOYDB_DATABASE_NAME", "").strip(),
        alloydb_table_name=os.getenv("ALLOYDB_TABLE_NAME", "").strip(),
        alloydb_cluster_name=os.getenv("ALLOYDB_CLUSTER_NAME", "").strip(),
        alloydb_instance_name=os.getenv("ALLOYDB_INSTANCE_NAME", "").strip(),
        alloydb_secret_name=os.getenv("ALLOYDB_SECRET_NAME", "").strip(),
        alloydb_user=os.getenv("ALLOYDB_USER", "postgres").strip(),
        alloydb_password=os.getenv("ALLOYDB_PASSWORD", "").strip(),
        port=int(os.getenv("PORT", "8080")),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        retry_backoff_seconds=float(os.getenv("RETRY_BACKOFF_SECONDS", "0.4")),
        circuit_breaker_failure_threshold=int(
            os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "4")
        ),
        circuit_breaker_reset_seconds=int(os.getenv("CIRCUIT_BREAKER_RESET_SECONDS", "30")),
        rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
        rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
        enable_tracing=os.getenv("ENABLE_TRACING", "0") == "1",
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "shoppingassistantservice"),
        otel_collector_endpoint=os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
        ),
    )


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _log_event(level: str, event: str, **fields: Any) -> None:
    payload = {
        "ts": time.time(),
        "level": level,
        "event": event,
        "trace_id": getattr(g, "trace_id", ""),
    }
    payload.update(fields)
    line = json.dumps(payload, ensure_ascii=False)
    if level == "error":
        logging.error(line)
    elif level == "warning":
        logging.warning(line)
    else:
        logging.info(line)


def _init_tracing(config: AppConfig):
    if not config.enable_tracing:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": config.otel_service_name})
        )
        exporter = OTLPSpanExporter(endpoint=config.otel_collector_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return trace.get_tracer(config.otel_service_name)
    except Exception as err:  # pylint: disable=broad-exception-caught
        logging.warning(
            json.dumps(
                {
                    "level": "warning",
                    "event": "tracing_init_failed",
                    "error": str(err),
                },
                ensure_ascii=False,
            )
        )
        return None


def _resolve_alloydb_password(config: AppConfig) -> str:
    if config.alloydb_password:
        return config.alloydb_password
    if not (config.alloydb_project_id and config.alloydb_secret_name):
        raise ValueError(
            "ALLOYDB_PASSWORD or PROJECT_ID + ALLOYDB_SECRET_NAME must be configured."
        )
    secret_manager_client = secretmanager_v1.SecretManagerServiceClient()
    secret_name = secret_manager_client.secret_version_path(
        project=config.alloydb_project_id,
        secret=config.alloydb_secret_name,
        secret_version="latest",
    )
    secret_request = secretmanager_v1.AccessSecretVersionRequest(name=secret_name)
    secret_response = secret_manager_client.access_secret_version(request=secret_request)
    return secret_response.payload.data.decode("UTF-8").strip()


def _normalize_tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-zA-Z0-9]+", text.lower()) if token}


def _safe_url_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or ""


def _extract_product_ids(relevant_docs: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for doc in relevant_docs:
        if "id" in doc and isinstance(doc["id"], str):
            ids.append(doc["id"])
            continue
        raw = doc.get("raw")
        if isinstance(raw, dict):
            metadata = raw.get("kwargs", {}).get("metadata", {})
            if isinstance(metadata, dict) and isinstance(metadata.get("id"), str):
                ids.append(metadata["id"])
        metadata = doc.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("id"), str):
            ids.append(metadata["id"])
    deduped = []
    seen = set()
    for pid in ids:
        if pid not in seen:
            deduped.append(pid)
            seen.add(pid)
    return deduped


def _load_prompt_template(prompt_dir: Path, filename: str, fallback: str) -> str:
    prompt_file = prompt_dir / filename
    if not prompt_file.is_file():
        return fallback
    return prompt_file.read_text(encoding="utf-8").strip()


def _ensure_recommendation_id_format(text: str, fallback_ids: list[str]) -> str:
    if PRODUCT_ID_PATTERN.search(text):
        return text
    best = fallback_ids[:3]
    if not best:
        best = ["NO_MATCH"]
    suffix = ", ".join(f"[{item}]" for item in best)
    return f"{text.rstrip()}\n推荐ID: {suffix}"


class CatalogRetriever:
    def __init__(self, config: AppConfig):
        self._config = config
        self._vectorstore: AlloyDBVectorStore | None = None
        self._fallback_products: list[dict[str, Any]] = []
        self._backend = config.vectorstore_backend
        self._init_backend()

    @property
    def backend(self) -> str:
        return self._backend

    def _init_backend(self) -> None:
        if self._backend == "alloydb":
            try:
                password = _resolve_alloydb_password(self._config)
                engine = AlloyDBEngine.from_instance(
                    project_id=self._config.alloydb_project_id,
                    region=self._config.alloydb_region,
                    cluster=self._config.alloydb_cluster_name,
                    instance=self._config.alloydb_instance_name,
                    database=self._config.alloydb_database_name,
                    user=self._config.alloydb_user,
                    password=password,
                )
                self._vectorstore = AlloyDBVectorStore.create_sync(
                    engine=engine,
                    table_name=self._config.alloydb_table_name,
                    embedding_service=GoogleGenerativeAIEmbeddings(
                        model="models/embedding-001"
                    ),
                    id_column="id",
                    content_column="description",
                    embedding_column="product_embedding",
                    metadata_columns=["id", "name", "categories"],
                )
                return
            except Exception as err:  # pylint: disable=broad-exception-caught
                logging.warning(
                    json.dumps(
                        {
                            "level": "warning",
                            "event": "alloydb_unavailable_fallback_json",
                            "error": str(err),
                        },
                        ensure_ascii=False,
                    )
                )
                self._backend = "json"

        if self._backend == "json":
            catalog_path = Path(self._config.product_catalog_json)
            if catalog_path.is_file():
                with catalog_path.open("r", encoding="utf-8") as f:
                    products = json.load(f)
                self._fallback_products = products if isinstance(products, list) else []
            else:
                logging.warning(
                    json.dumps(
                        {
                            "level": "warning",
                            "event": "json_catalog_not_found",
                            "path": str(catalog_path),
                        },
                        ensure_ascii=False,
                    )
                )

    def similarity_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        RETRIEVAL_QUERY_COUNTER.labels(backend=self._backend).inc()

        if self._vectorstore is not None:
            docs = self._vectorstore.similarity_search(query, k=limit)
            normalized_docs: list[dict[str, Any]] = []
            for doc in docs:
                if hasattr(doc, "to_json"):
                    normalized_docs.append({"raw": doc.to_json()})
                else:
                    normalized_docs.append(
                        {
                            "content": getattr(doc, "page_content", ""),
                            "metadata": getattr(doc, "metadata", {}),
                        }
                    )
            RETRIEVAL_HIT_COUNTER.labels(backend=self._backend).inc(len(normalized_docs))
            ratio = 0.0 if not normalized_docs else 1.0
            RETRIEVAL_HIT_RATIO.labels(backend=self._backend).set(ratio)
            return normalized_docs

        query_tokens = _normalize_tokens(query)
        scored: list[tuple[int, dict[str, Any]]] = []
        for product in self._fallback_products:
            feature_text = " ".join(
                [
                    str(product.get("name", "")),
                    str(product.get("description", "")),
                    " ".join(product.get("categories", [])),
                ]
            )
            overlap = len(query_tokens & _normalize_tokens(feature_text))
            if overlap > 0:
                JSON_RELEVANCE_SCORE.observe(overlap)
                cloned = dict(product)
                cloned["_relevance_score"] = overlap
                scored.append((overlap, cloned))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item[1] for item in scored[:limit]]
        RETRIEVAL_HIT_COUNTER.labels(backend=self._backend).inc(len(results))
        ratio = len(results) / max(1, min(limit, len(self._fallback_products) or 1))
        RETRIEVAL_HIT_RATIO.labels(backend=self._backend).set(ratio)
        return results


class DesignModelClient:
    def __init__(self, config: AppConfig, circuit_breaker: CircuitBreaker):
        self._config = config
        self._provider = config.model_provider
        self._circuit_breaker = circuit_breaker
        self._gemini_vision: ChatGoogleGenerativeAI | None = None
        self._gemini_text: ChatGoogleGenerativeAI | None = None
        self._prompt_dir = Path(os.getenv("PROMPT_TEMPLATE_DIR", str(DEFAULT_PROMPT_DIR)))
        self._prompt_describe_with_image = _load_prompt_template(
            self._prompt_dir,
            "describe_room_with_image.txt",
            "You are a professional interior designer. Provide a concise style description for this room image.",
        )
        self._prompt_describe_without_image = _load_prompt_template(
            self._prompt_dir,
            "describe_room_without_image.txt",
            "You are a professional interior designer. The user did not provide an image. Ask clarifying questions and infer style hints from text.",
        )
        self._prompt_recommend = _load_prompt_template(
            self._prompt_dir,
            "recommend_products.txt",
            "你是 however 微服务商城中的室内搭配顾问。",
        )

        if self._provider == "gemini":
            self._gemini_vision = ChatGoogleGenerativeAI(model=config.gemini_vision_model)
            self._gemini_text = ChatGoogleGenerativeAI(model=config.gemini_text_model)

        if self._provider == "ollama":
            host = _safe_url_host(config.ollama_base_url)
            if config.ollama_allowed_hosts and host not in config.ollama_allowed_hosts:
                raise ValueError(
                    f"OLLAMA_BASE_URL host '{host}' is not in OLLAMA_ALLOWED_HOSTS"
                )

    def describe_room(self, image_url: str) -> str:
        if self._provider == "ollama":
            prompt = (
                "你是一名室内设计顾问。请根据以下图片链接推断空间风格、主色调、材质和氛围。"
                f"图片链接：{image_url or '未提供'}"
            )
            return self._call_with_retry(lambda: self._call_ollama(prompt), "describe_room")

        if not image_url:
            return self._call_with_retry(
                lambda: str(
                    cast(ChatGoogleGenerativeAI, self._gemini_text)
                    .invoke(self._prompt_describe_without_image)
                    .content
                ),
                "describe_room_without_image",
            )

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": self._prompt_describe_with_image,
                },
                {"type": "image_url", "image_url": image_url},
            ]
        )
        return self._call_with_retry(
            lambda: str(
                cast(ChatGoogleGenerativeAI, self._gemini_vision).invoke([message]).content
            ),
            "describe_room_with_image",
        )

    def recommend_products(
        self, room_description: str, relevant_docs: str, customer_prompt: str
    ) -> str:
        if not self._circuit_breaker.can_call():
            return self._degraded_response(customer_prompt)

        design_prompt = (
            f"{self._prompt_recommend}\n"
            f"房间风格描述：{room_description}\n"
            f"候选商品信息：{relevant_docs}\n"
            f"用户诉求：{customer_prompt}\n"
            "请先用 1-2 句话复述房间风格，再给出推荐理由和商品建议。"
            "若候选商品都不匹配，请明确说明。"
            "最后请按 [id1], [id2], [id3] 格式列出你认为最相关的 3 个商品 ID。"
        )

        try:
            if self._provider == "ollama":
                result = self._call_with_retry(
                    lambda: self._call_ollama(design_prompt), "recommend_products_ollama"
                )
            else:
                result = self._call_with_retry(
                    lambda: str(
                        cast(ChatGoogleGenerativeAI, self._gemini_text)
                        .invoke(design_prompt)
                        .content
                    ),
                    "recommend_products_gemini",
                )
            self._circuit_breaker.mark_success()
            return result
        except Exception as err:  # pylint: disable=broad-exception-caught
            self._circuit_breaker.mark_failure()
            logging.error(
                json.dumps(
                    {
                        "level": "error",
                        "event": "recommend_products_failed",
                        "error": str(err),
                    },
                    ensure_ascii=False,
                )
            )
            return self._degraded_response(customer_prompt)

    def _degraded_response(self, customer_prompt: str) -> str:
        return (
            "当前智能推荐通道处于保护模式，已启用降级回复。"
            f"\n你可继续描述偏好（当前输入：{customer_prompt}），系统将返回基础推荐。\n推荐ID: [NO_MATCH]"
        )

    def _call_with_retry(self, fn: Callable[[], str], operation: str) -> str:
        last_error = None
        for attempt in range(self._config.max_retries + 1):
            try:
                return fn()
            except Exception as err:  # pylint: disable=broad-exception-caught
                last_error = err
                if attempt >= self._config.max_retries:
                    break
                sleep_seconds = self._config.retry_backoff_seconds * (2 ** attempt)
                logging.warning(
                    json.dumps(
                        {
                            "level": "warning",
                            "event": "retry_scheduled",
                            "operation": operation,
                            "attempt": attempt + 1,
                            "sleep_seconds": sleep_seconds,
                            "error": str(err),
                        },
                        ensure_ascii=False,
                    )
                )
                time.sleep(sleep_seconds)
        raise RuntimeError(f"operation={operation} failed after retries: {last_error}")

    def _call_ollama(self, prompt: str) -> str:
        endpoint = f"{self._config.ollama_base_url}/api/generate"
        payload = {
            "model": self._config.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        response = requests.post(
            endpoint, json=payload, timeout=self._config.ollama_timeout_seconds
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("response", ""))


def create_app(config: AppConfig | None = None) -> Flask:
    _configure_logging()
    config = config or _build_config()

    app = Flask(__name__)
    tracer = _init_tracing(config)
    limiter = RateLimiter(
        window_seconds=config.rate_limit_window_seconds,
        max_requests=config.rate_limit_max_requests,
    )
    circuit_breaker = CircuitBreaker(
        failure_threshold=config.circuit_breaker_failure_threshold,
        reset_seconds=config.circuit_breaker_reset_seconds,
    )
    retriever = CatalogRetriever(config)
    model_client = DesignModelClient(config, circuit_breaker)

    @app.before_request
    def before_request_hook():
        g.trace_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        g.request_start = time.time()
        remote = request.headers.get("x-forwarded-for", request.remote_addr or "unknown")
        if not limiter.allow(remote):
            RATE_LIMIT_REJECT_COUNTER.inc()
            _log_event("warning", "rate_limit_rejected", remote=remote)
            return {"error": "rate limit exceeded"}, 429
        return None

    @app.after_request
    def after_request_hook(response):
        elapsed = time.time() - getattr(g, "request_start", time.time())
        REQUEST_LATENCY.labels(
            provider=config.model_provider,
            backend=retriever.backend,
        ).observe(elapsed)
        return response

    @app.route("/", methods=["POST"])
    def design_assistant():
        payload = request.get_json(silent=True) or {}
        try:
            req_obj = AssistantRequest(**payload)
        except ValidationError as err:
            REQUEST_COUNTER.labels(
                status="bad_request",
                provider=config.model_provider,
                backend=retriever.backend,
            ).inc()
            _log_event("warning", "invalid_request", errors=err.errors())
            return {"error": "invalid request", "details": err.errors()}, 400

        span_ctx = (
            tracer.start_as_current_span("design_assistant_request")
            if tracer is not None
            else None
        )

        try:
            if span_ctx is not None:
                span_ctx.__enter__()

            _log_event(
                "info",
                "request_started",
                provider=config.model_provider,
                backend=retriever.backend,
            )
            room_description = model_client.describe_room(req_obj.image)
            vector_search_prompt = (
                f"用户需求：{req_obj.message}。请从商品目录中检索与以下房间风格最匹配的商品：{room_description}"
            )
            docs = retriever.similarity_search(vector_search_prompt, config.vector_top_k)
            candidate_ids = _extract_product_ids(docs)
            relevant_docs = ", ".join([json.dumps(doc, ensure_ascii=False) for doc in docs])
            content = model_client.recommend_products(
                room_description=room_description,
                relevant_docs=relevant_docs,
                customer_prompt=req_obj.message,
            )
            content = _ensure_recommendation_id_format(content, candidate_ids)

            REQUEST_COUNTER.labels(
                status="ok",
                provider=config.model_provider,
                backend=retriever.backend,
            ).inc()
            _log_event(
                "info",
                "request_completed",
                retrieved_docs=len(docs),
                candidate_ids=candidate_ids[:3],
            )
            return {"content": content, "trace_id": g.trace_id}
        except Exception as err:  # pylint: disable=broad-exception-caught
            REQUEST_COUNTER.labels(
                status="error",
                provider=config.model_provider,
                backend=retriever.backend,
            ).inc()
            _log_event("error", "request_failed", error=str(err))
            return {"error": "internal error", "trace_id": g.trace_id}, 500
        finally:
            if span_ctx is not None:
                span_ctx.__exit__(None, None, None)

    @app.route("/healthz", methods=["GET"])
    def health_check():
        return {
            "status": "ok",
            "model_provider": config.model_provider,
            "vectorstore_backend": retriever.backend,
            "circuit_breaker_open": not circuit_breaker.can_call(),
        }

    @app.route("/readyz", methods=["GET"])
    def readiness_check():
        backend_ready = retriever.backend in ("alloydb", "json")
        provider_ready = config.model_provider in ("gemini", "ollama")
        status_code = 200 if (backend_ready and provider_ready) else 503
        return {
            "ready": backend_ready and provider_ready,
            "backend": retriever.backend,
            "provider": config.model_provider,
        }, status_code

    @app.route("/livez", methods=["GET"])
    def liveness_check():
        return {"alive": True}

    @app.route("/metrics", methods=["GET"])
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    return app


if __name__ == "__main__":
    runtime_config = _build_config()
    app = create_app(runtime_config)
    app.run(host="0.0.0.0", port=runtime_config.port)
