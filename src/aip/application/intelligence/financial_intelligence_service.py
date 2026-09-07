from __future__ import annotations

from aip.application.intelligence.context_provider import FinancialIntelligenceContextProvider
from aip.application.intelligence.llm_gateway import DisabledLLMGateway, LLMGateway
from aip.domain.intelligence.engine import FinancialIntelligenceEngine
from aip.domain.intelligence.models import FinancialIntelligenceContext, FinancialIntelligenceReport


class FinancialIntelligenceService:
    """Application facade for deterministic alerts and optional generative reasoning."""

    def __init__(
        self,
        context_provider: FinancialIntelligenceContextProvider,
        *,
        engine: FinancialIntelligenceEngine | None = None,
        llm_gateway: LLMGateway | None = None,
    ) -> None:
        self._context_provider = context_provider
        self._engine = engine or FinancialIntelligenceEngine()
        self._llm_gateway = llm_gateway or DisabledLLMGateway()
        self._context: FinancialIntelligenceContext | None = None
        self._report: FinancialIntelligenceReport | None = None

    @property
    def llm_provider_name(self) -> str:
        return self._llm_gateway.provider_name

    @property
    def llm_available(self) -> bool:
        return self._llm_gateway.available

    def analyze(self, *, force_refresh: bool = False) -> FinancialIntelligenceReport:
        if self._report is not None and not force_refresh:
            return self._report
        self._context = self._context_provider.load()
        self._report = self._engine.analyze(self._context)
        return self._report

    def ask(self, question: str) -> str:
        report = self.analyze()
        context = self._context
        if context is None:
            raise RuntimeError("El contexto de inteligencia no está disponible")
        if self._llm_gateway.available:
            return self._llm_gateway.answer(context, question)
        return self._engine.answer(report, question)
