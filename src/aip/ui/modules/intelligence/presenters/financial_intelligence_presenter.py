from __future__ import annotations

from aip.application.intelligence.financial_intelligence_service import (
    FinancialIntelligenceService,
)
from aip.application.intelligence.llm_gateway import LLMGateway
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.intelligence.aip_context_provider import (
    AIPFinancialIntelligenceContextProvider,
)
from aip.product.intelligence.llm_gateway_factory import build_llm_gateway
from aip.ui.modules.intelligence.viewmodels.financial_intelligence_view_model import (
    FinancialIntelligenceViewModel,
    IntelligenceFindingRow,
)


class FinancialIntelligencePresenter:
    """Adapt the intelligence application service into a passive UI model."""

    def __init__(
        self,
        application_factory: DemoApplicationFactory,
        *,
        llm_gateway: LLMGateway | None = None,
    ) -> None:
        self._service = FinancialIntelligenceService(
            AIPFinancialIntelligenceContextProvider(application_factory),
            llm_gateway=llm_gateway or build_llm_gateway(),
        )

    def build_view_model(self, *, force_refresh: bool = False) -> FinancialIntelligenceViewModel:
        report = self._service.analyze(force_refresh=force_refresh)
        rows = tuple(
            IntelligenceFindingRow(
                severity=item.severity.value,
                domain=item.domain,
                title=item.title,
                summary=item.summary,
                recommendation=item.recommendation,
                evidence=" · ".join(
                    f"{evidence.metric}: {evidence.value} ({evidence.source})"
                    for evidence in item.evidence
                ),
                policy_reference=item.policy_reference,
            )
            for item in report.findings
        )
        return FinancialIntelligenceViewModel(
            cutoff_date=report.cutoff_date.strftime("%d/%m/%Y"),
            mode=report.mode,
            llm_provider=self._service.llm_provider_name,
            llm_available=self._service.llm_available,
            coverage=" · ".join(report.coverage),
            alert_count=report.alert_count,
            opportunity_count=report.opportunity_count,
            executive_summary=report.executive_summary,
            findings=rows,
            warnings=report.warnings,
        )

    def ask(self, question: str) -> str:
        return self._service.ask(question)
