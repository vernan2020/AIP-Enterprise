from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    AuditedPortfolioScenario,
    PortfolioScenarioEvidenceBridge,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy
from aip.product.configured.adapters.institutional_portfolio_scenario_adapter import (
    InstitutionalMasterScenarioRiskAdapter,
    VerifiedScenarioFXRate,
)


class ConfiguredPortfolioSnapshot(Protocol):
    """Only the existing configured provider's public payload is required."""

    def get_portfolio(self) -> dict[str, Any]: ...


class ConfiguredInstitutionalScenarioService:
    """Orchestrate an institutional master selected by existing folder configuration.

    A fresh reader pass verifies native market-value fields: the configured
    dashboard's potentially substituted/rounded values are never used as
    regulatory exposures or as scenario valuation sources.
    """

    def __init__(self, provider: ConfiguredPortfolioSnapshot) -> None:
        self._provider = provider

    def evaluate(
        self,
        capital_positions: Sequence[VerifiedCapitalPosition],
        source_row_by_position: Mapping[str, int] | None,
        proposed_weights: Mapping[str, Decimal],
        *,
        cutoff: date,
        policy: ScenarioRiskPolicy,
        fx_rates_by_currency: Mapping[str, VerifiedScenarioFXRate] | None = None,
    ) -> AuditedPortfolioScenario:
        snapshot = self._provider.get_portfolio()
        if snapshot.get("data_quality_status") != "HEALTHY":
            raise ValueError("Configured institutional portfolio source quality is not healthy")
        if str(snapshot.get("valuation_date") or "") != cutoff.isoformat():
            raise ValueError("Configured portfolio cutoff does not match requested scenario")
        selection = snapshot.get("portfolio_master")
        if not isinstance(selection, dict) or selection.get("status") != "HEALTHY":
            raise ValueError("Institutional portfolio master has no verified source selection")
        if selection.get("valuation_date") != cutoff.isoformat():
            raise ValueError("Selected master date does not match requested cutoff")
        directory = selection.get("directory")
        filename = selection.get("file_name")
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError("Selected institutional master directory is unavailable")
        if (
            not isinstance(filename, str)
            or not filename.strip()
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or not filename.lower().endswith((".xls", ".xlsx"))
        ):
            raise ValueError("Selected institutional master filename is invalid")
        path = Path(directory) / filename
        market = InstitutionalMasterScenarioRiskAdapter.read_file(
            path,
            capital_positions,
            source_row_by_position,
            cutoff=cutoff,
            fx_rates_by_currency=fx_rates_by_currency,
        )
        return PortfolioScenarioEvidenceBridge.compare(
            capital_positions,
            market.market_risks,
            proposed_weights,
            cutoff=cutoff,
            portfolio_market_value_crc=market.total_market_value_crc,
            portfolio_valuation_source=market.master_file,
            policy=policy,
        )
