import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, cast
from urllib.parse import urlparse

import requests
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from config import DEFAULT_PROMPT_DIR, AppConfig
from resilience import CircuitBreaker

PRODUCT_ID_PATTERN = re.compile(r"\[([A-Za-z0-9_-]{3,64})\]")


def _safe_url_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or ""


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
    suffix = ", ".join([f"[{item}]" for item in best])
    return f"{text.rstrip()}\n推荐ID: {suffix}"


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
