from __future__ import annotations

from typing import Protocol

from aip.domain.intelligence.models import FinancialIntelligenceContext


class LLMGateway(Protocol):
    """Provider-neutral generative analysis port for AIP Enterprise."""

    @property
    def provider_name(self) -> str: ...

    @property
    def available(self) -> bool: ...

    def answer(self, context: FinancialIntelligenceContext, question: str) -> str: ...


class DisabledLLMGateway:
    """Safe default until an institutional LLM provider is configured."""

    @property
    def provider_name(self) -> str:
        return "NO CONFIGURADO"

    @property
    def available(self) -> bool:
        return False

    def answer(self, context: FinancialIntelligenceContext, question: str) -> str:
        del context, question
        raise RuntimeError("No existe un proveedor LLM institucional configurado")
