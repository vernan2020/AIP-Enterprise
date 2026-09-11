from __future__ import annotations

from typing import Protocol

from aip.domain.intelligence.models import (
    FinancialIntelligenceContext,
    FinancialIntelligenceReport,
)


class LLMGateway(Protocol):
    """Provider-neutral generative analysis port for AIP Enterprise."""

    @property
    def provider_name(self) -> str: ...

    @property
    def available(self) -> bool: ...

    def answer(
        self,
        context: FinancialIntelligenceContext,
        report: FinancialIntelligenceReport,
        question: str,
    ) -> str: ...


class DisabledLLMGateway:
    """Safe default when no institutional LLM provider is enabled."""

    def __init__(
        self,
        *,
        provider_name: str = "NO CONFIGURADO",
        reason: str = "No existe un proveedor LLM institucional configurado",
    ) -> None:
        self._provider_name = provider_name
        self._reason = reason

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def available(self) -> bool:
        return False

    def answer(
        self,
        context: FinancialIntelligenceContext,
        report: FinancialIntelligenceReport,
        question: str,
    ) -> str:
        del context, report, question
        raise RuntimeError(self._reason)
