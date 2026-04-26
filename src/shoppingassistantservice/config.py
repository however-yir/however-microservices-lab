import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field, field_validator

DEFAULT_PRODUCT_CATALOG = Path(__file__).resolve().parent / "products.local.json"
DEFAULT_PROMPT_DIR = Path(__file__).resolve().parent / "prompts" / "v1"
SUPPORTED_MODEL_PROVIDERS = {"gemini", "ollama"}
SUPPORTED_VECTOR_BACKENDS = {"alloydb", "json"}


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


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as err:
        raise ValueError(f"{name} must be an integer") from err


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as err:
        raise ValueError(f"{name} must be a number") from err


def _build_config() -> AppConfig:
    allowlist = tuple(
        host.strip()
        for host in os.getenv("OLLAMA_ALLOWED_HOSTS", "ollama,127.0.0.1,localhost").split(",")
        if host.strip()
    )
    config = AppConfig(
        model_provider=os.getenv("MODEL_PROVIDER", "gemini").strip().lower(),
        gemini_vision_model=os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash"),
        gemini_text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-1.5-flash"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout_seconds=_int_env("OLLAMA_TIMEOUT_SECONDS", 60),
        ollama_allowed_hosts=allowlist,
        vectorstore_backend=os.getenv("VECTORSTORE_BACKEND", "alloydb").strip().lower(),
        vector_top_k=_int_env("VECTOR_TOP_K", 6),
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
        port=_int_env("PORT", 8080),
        max_retries=_int_env("MAX_RETRIES", 2),
        retry_backoff_seconds=_float_env("RETRY_BACKOFF_SECONDS", 0.4),
        circuit_breaker_failure_threshold=_int_env("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 4),
        circuit_breaker_reset_seconds=_int_env("CIRCUIT_BREAKER_RESET_SECONDS", 30),
        rate_limit_window_seconds=_int_env("RATE_LIMIT_WINDOW_SECONDS", 60),
        rate_limit_max_requests=_int_env("RATE_LIMIT_MAX_REQUESTS", 60),
        enable_tracing=os.getenv("ENABLE_TRACING", "0") == "1",
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "shoppingassistantservice"),
        otel_collector_endpoint=os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
        ),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    errors: list[str] = []
    if config.model_provider not in SUPPORTED_MODEL_PROVIDERS:
        errors.append(
            f"MODEL_PROVIDER must be one of {sorted(SUPPORTED_MODEL_PROVIDERS)}"
        )
    if config.vectorstore_backend not in SUPPORTED_VECTOR_BACKENDS:
        errors.append(
            f"VECTORSTORE_BACKEND must be one of {sorted(SUPPORTED_VECTOR_BACKENDS)}"
        )
    if config.vector_top_k < 1:
        errors.append("VECTOR_TOP_K must be >= 1")
    if config.port < 1 or config.port > 65535:
        errors.append("PORT must be between 1 and 65535")
    if config.max_retries < 0:
        errors.append("MAX_RETRIES must be >= 0")
    if config.retry_backoff_seconds < 0:
        errors.append("RETRY_BACKOFF_SECONDS must be >= 0")
    if config.circuit_breaker_failure_threshold < 1:
        errors.append("CIRCUIT_BREAKER_FAILURE_THRESHOLD must be >= 1")
    if config.rate_limit_window_seconds < 1:
        errors.append("RATE_LIMIT_WINDOW_SECONDS must be >= 1")
    if config.rate_limit_max_requests < 1:
        errors.append("RATE_LIMIT_MAX_REQUESTS must be >= 1")

    parsed_ollama = urlparse(config.ollama_base_url)
    if config.model_provider == "ollama":
        if parsed_ollama.scheme not in {"http", "https"} or not parsed_ollama.hostname:
            errors.append("OLLAMA_BASE_URL must be an http(s) URL with a host")
        elif (
            config.ollama_allowed_hosts
            and parsed_ollama.hostname not in config.ollama_allowed_hosts
        ):
            errors.append(
                f"OLLAMA_BASE_URL host '{parsed_ollama.hostname}' is not in OLLAMA_ALLOWED_HOSTS"
            )

    if config.vectorstore_backend == "json" and not Path(config.product_catalog_json).is_file():
        errors.append(f"PRODUCT_CATALOG_JSON does not exist: {config.product_catalog_json}")

    if config.vectorstore_backend == "alloydb":
        alloydb_ready = all(
            [
                config.alloydb_project_id,
                config.alloydb_region,
                config.alloydb_database_name,
                config.alloydb_table_name,
                config.alloydb_cluster_name,
                config.alloydb_instance_name,
                config.alloydb_password or config.alloydb_secret_name,
            ]
        )
        has_json_fallback = Path(config.product_catalog_json).is_file()
        if not alloydb_ready and not has_json_fallback:
            errors.append(
                "AlloyDB configuration is incomplete and PRODUCT_CATALOG_JSON fallback is unavailable"
            )

    if errors:
        raise ValueError("; ".join(errors))
