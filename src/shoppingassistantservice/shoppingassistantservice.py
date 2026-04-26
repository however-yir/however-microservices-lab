#!/usr/bin/python

import json
import logging
import time
import uuid
from typing import Any

import requests  # noqa: F401 - re-exported for existing tests and monkeypatches.
from flask import Flask, Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import ValidationError

from config import AppConfig, AssistantRequest, _build_config
from metrics import RATE_LIMIT_REJECT_COUNTER, REQUEST_COUNTER, REQUEST_LATENCY
from model_client import DesignModelClient, _ensure_recommendation_id_format
from resilience import CircuitBreaker, RateLimiter
from retriever import CatalogRetriever, _extract_product_ids


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
