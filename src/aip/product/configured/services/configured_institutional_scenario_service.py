from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ApprovedMasterAttestation:
    """Externally approved digest declaration, not a digital signature.

    The operator must independently verify approval_reference and sha256.
    Comparing a supplied digest proves only equality with that declaration.
    """

    cutoff: date
    master_file: str
    sheet_name: str
    sha256: str
    approval_reference: str


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
        master_attestation: ApprovedMasterAttestation | None = None,
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
        if path.is_symlink() or path.resolve().parent != Path(directory).resolve():
            raise ValueError("Selected master must be a regular file inside its configured directory")
        if master_attestation is not None:
            attestation = master_attestation
            if (
                attestation.cutoff != cutoff
                or not Path(attestation.master_file).is_absolute()
                or Path(attestation.master_file).resolve() != path.resolve()
                or not attestation.sheet_name.strip()
                or not attestation.approval_reference.strip()
                or re.fullmatch(r"[0-9a-f]{64}", attestation.sha256) is None
            ):
                raise ValueError("Approved master attestation is invalid for this cutoff or file")
        market = InstitutionalMasterScenarioRiskAdapter.read_file(
            path,
            capital_positions,
            source_row_by_position,
            cutoff=cutoff,
            fx_rates_by_currency=fx_rates_by_currency,
        )
        if master_attestation is not None and (
            market.master_sha256 != master_attestation.sha256
            or market.sheet_name != master_attestation.sheet_name
            or market.cutoff != master_attestation.cutoff
        ):
            raise ValueError("Master digest or sheet differs from approved attestation")
        source_reference = (
            f"{market.master_file}|sha256:{market.master_sha256}"
            if market.master_sha256
            else market.master_file
        )
        source_reference += (
            f"|manifest-match:{master_attestation.approval_reference}"
            if master_attestation is not None
            else "|manifest-not-supplied"
        )
        return PortfolioScenarioEvidenceBridge.compare(
            capital_positions,
            market.market_risks,
            proposed_weights,
            cutoff=cutoff,
            portfolio_market_value_crc=market.total_market_value_crc,
            portfolio_valuation_source=source_reference,
            policy=policy,
        )
