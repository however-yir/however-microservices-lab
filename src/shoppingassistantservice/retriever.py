import json
import logging
import re
from pathlib import Path
from typing import Any

from google.cloud import secretmanager_v1
from langchain_google_alloydb_pg import AlloyDBEngine, AlloyDBVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from config import AppConfig
from metrics import (
    JSON_RELEVANCE_SCORE,
    RETRIEVAL_HIT_COUNTER,
    RETRIEVAL_HIT_RATIO,
    RETRIEVAL_QUERY_COUNTER,
)


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
    for product_id in ids:
        if product_id not in seen:
            deduped.append(product_id)
            seen.add(product_id)
    return deduped


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
                with catalog_path.open("r", encoding="utf-8") as catalog:
                    products = json.load(catalog)
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

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [item[1] for item in scored[:limit]]
        RETRIEVAL_HIT_COUNTER.labels(backend=self._backend).inc(len(results))
        ratio = len(results) / max(1, min(limit, len(self._fallback_products) or 1))
        RETRIEVAL_HIT_RATIO.labels(backend=self._backend).set(ratio)
        return results
