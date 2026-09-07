from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from aip.domain.financial_analysis.models import (
    EntityFinancialSummary,
    FinancialAnalysisSnapshot,
    FinancialEntity,
    FinancialMetric,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)
from aip.product.intelligence.aip_context_provider import (
    AIPFinancialIntelligenceContextProvider,
)


class _FinancialService:
    def __init__(
        self, selected: FinancialEntity, peers: tuple[EntityFinancialSummary, ...]
    ) -> None:
        self._selected = selected
        self._peers = peers
        self.calls: list[date] = []

    def load(
        self,
        *,
        selected_entity_id: str | None = None,
        cutoff_date: date | None = None,
        force_refresh: bool = False,
    ) -> FinancialAnalysisSnapshot:
        assert selected_entity_id == self._selected.entity_id
        assert cutoff_date is not None
        self.calls.append(cutoff_date)
        if cutoff_date == date(2026, 8, 31):
            return FinancialAnalysisSnapshot(
                status="UNAVAILABLE",
                cutoff_date=cutoff_date,
                selected_entity=None,
            )
        return FinancialAnalysisSnapshot(
            status="AVAILABLE",
            cutoff_date=date(2026, 7, 31),
            selected_entity=self._selected,
            entities=(self._selected,),
            metrics=(
                FinancialMetric(
                    code="ROA",
                    label="ROA",
                    value=Decimal("1.02"),
                    unit="PERCENT",
                ),
            ),
            peer_summaries=self._peers,
        )


class _Container:
    def __init__(self, service: _FinancialService) -> None:
        self._service = service

    def resolve(self, service_type: object) -> object:
        assert service_type is ConfiguredFinancialAnalysisService
        return self._service


def _provider(service: _FinancialService) -> AIPFinancialIntelligenceContextProvider:
    factory = SimpleNamespace(
        container=_Container(service),
        configured_source_config=SimpleNamespace(
            sugef_financial=SimpleNamespace(api_entity_codes=(service._selected.entity_id,))
        ),
    )
    return AIPFinancialIntelligenceContextProvider(factory)  # type: ignore[arg-type]


def test_financial_context_falls_back_to_latest_available_sugef_month() -> None:
    selected = FinancialEntity("3004045138", "COOPEALIANZA R.L.", "COOPERATIVAS")
    peer = EntityFinancialSummary(
        entity=FinancialEntity("PEER-1", "COOPERATIVA PAR", "COOPERATIVAS"),
        statement_date=date(2026, 7, 31),
        assets=Decimal("500000000000"),
        roa_percent=Decimal("0.80"),
    )
    service = _FinancialService(selected, (peer,))

    context = _provider(service)._resolve_financial_analysis(date(2026, 8, 31))

    assert service.calls == [date(2026, 8, 31), date(2026, 7, 31)]
    assert context.status == "AVAILABLE"
    assert context.cutoff_date == date(2026, 7, 31)
    assert context.entity_name == "COOPEALIANZA R.L."
    assert len(context.peers) == 1
    assert context.peers[0].entity_name == "COOPERATIVA PAR"


def test_financial_peer_selection_keeps_full_available_universe() -> None:
    selected = FinancialEntity("MAIN", "COOPEALIANZA R.L.", "COOPERATIVAS")
    peers = tuple(
        EntityFinancialSummary(
            entity=FinancialEntity(
                f"PEER-{index}",
                f"ENTIDAD {index}",
                "COOPERATIVAS" if index % 2 == 0 else "BANCOS",
            ),
            statement_date=date(2026, 7, 31),
            assets=Decimal(index + 1) * Decimal("1000000"),
        )
        for index in range(25)
    )

    selected_peers = AIPFinancialIntelligenceContextProvider._select_financial_peers(
        peers,
        selected,
    )

    assert len(selected_peers) == 25
    assert {item.entity.entity_id for item in selected_peers} == {
        f"PEER-{index}" for index in range(25)
    }
