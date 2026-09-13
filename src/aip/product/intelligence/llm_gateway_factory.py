from __future__ import annotations

import os

from loguru import logger

from aip.application.intelligence.llm_gateway import DisabledLLMGateway, LLMGateway
from aip.product.intelligence.openai_responses_gateway import OpenAIResponsesGateway


def build_llm_gateway() -> LLMGateway:
    """Build the configured LLM adapter without ever persisting credentials."""

    if not _env_bool("AIP_LLM_ENABLED", default=False):
        return DisabledLLMGateway()

    provider = os.getenv("AIP_LLM_PROVIDER", "openai").strip().casefold()
    if provider != "openai":
        logger.warning("Unsupported AIP LLM provider requested: {}", provider or "<empty>")
        return DisabledLLMGateway(
            provider_name="PROVEEDOR NO SOPORTADO",
            reason=f"El proveedor LLM '{provider}' no está soportado por esta versión de AIP",
        )

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return DisabledLLMGateway(
            provider_name="OpenAI · SIN CLAVE",
            reason="AIP_LLM_ENABLED está activo pero OPENAI_API_KEY no está configurada",
        )

    model = os.getenv("AIP_LLM_MODEL", "gpt-5.6").strip() or "gpt-5.6"
    timeout_seconds = _bounded_float(
        "AIP_LLM_TIMEOUT_SECONDS",
        default=45.0,
        minimum=5.0,
        maximum=180.0,
    )
    max_output_tokens = _bounded_int(
        "AIP_LLM_MAX_OUTPUT_TOKENS",
        default=1400,
        minimum=256,
        maximum=6000,
    )

    logger.info(
        "Financial Copilot LLM enabled provider=OpenAI model={} timeout_seconds={} max_output_tokens={}",
        model,
        timeout_seconds,
        max_output_tokens,
    )
    return OpenAIResponsesGateway(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "y", "on", "si", "sí"}


def _bounded_int(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Invalid integer environment value {}={}; using default", name, raw)
        return default
    return min(maximum, max(minimum, value))


def _bounded_float(name: str, *, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Invalid numeric environment value {}={}; using default", name, raw)
        return default
    return min(maximum, max(minimum, value))
