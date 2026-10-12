from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    PortfolioScenarioEvidenceBridge,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy
from aip.product.configured.adapters.institutional_portfolio_scenario_adapter import (
    InstitutionalMasterScenarioRiskAdapter,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)

CUTOFF = date(2026, 10, 2)


def _positions() -> tuple[VerifiedCapitalPosition, ...]:
    def position(key: str, issuer: str, cls: ExposureClass) -> VerifiedCapitalPosition:
        return VerifiedCapitalPosition(
            position_key=key,
            isin=f"TEST-{key}",
            issuer=issuer,
            currency="CRC",
            cutoff=CUTOFF,
            invested_amount_crc=Decimal("500"),
            regulatory_exposure_crc=Decimal("200"),
            annual_net_yield=Decimal("0.05"),
            exposure_class=cls,
            classification_effective_date=CUTOFF,
            invested_amount_source="approved book fixture",
            regulatory_exposure_source="approved regulatory base fixture",
            net_yield_source="approved income fixture",
            classification_source="approved bucket fixture",
        )

    return (
        position("A", "G", ExposureClass.GOVERNMENT_CRC),
        position("B", "Issuer B", ExposureClass.UNRATED),
    )


def _master() -> InstitutionalPortfolioMasterReadResult:
    def row(key: str, number: int, issuer: str, classification: str, value: int) -> dict:
        return {
            "source_row": number,
            "source_currency": "CRC",
            "currency": "CRC",
            "isin": f"TEST-{key}",
            "issuer": issuer,
            "classification": classification,
            "product_code": "BONO",
            "market_value_crc": value,
            "principal_balance": value,
            "nominal_rate": 0.05,
            "portfolio_yield": 0.055,
            "periodicity": "semestral",
            "maturity_date": date(2028, 10, 2),
        }

    return InstitutionalPortfolioMasterReadResult(
        source_file="C:/audited/master-02-10-2026.xlsx",
        valuation_date=CUTOFF,
        sheet_selected="Cartera",
        normalized_positions=[
            row("B", 19, "Issuer B", "PRIVADA", 400),
            row("A", 17, "G", "D.V GOBIERNO", 600),
        ],
        warnings=(),
        rejected_row_count=0,
        source_status="HEALTHY",
        detected_column_mapping={
            key: key.upper()
            for key in (
                "market_value_crc",
                "currency",
                "issuer",
                "isin",
                "classification",
                "product_code",
                "principal_balance",
            )
        },
    )


def _adapt(master=None, positions=None, mapping=None):
    return InstitutionalMasterScenarioRiskAdapter.adapt(
        _master() if master is None else master,
        _positions() if positions is None else positions,
        {"A": 17, "B": 19} if mapping is None else mapping,
        cutoff=CUTOFF,
    )


def test_reader_to_institutional_engines_to_audited_scenario_bridge() -> None:
    evidence = _adapt()
    assert tuple(row.position_key for row in evidence.market_risks) == ("A", "B")
    assert evidence.total_market_value_crc == Decimal("1000")
    government, private = evidence.market_risks
    assert government.eligible_hqla_value_crc == Decimal("540.00")
    assert private.eligible_hqla_value_crc == Decimal("0")
    assert government.modified_duration_years > 0
    assert private.dv01_crc > 0
    assert "row:17" in government.market_value_source
    assert "duration:MODIFIED_DURATION" in government.duration_source
    policy = ScenarioRiskPolicy(
        cutoff=CUTOFF,
        effective_date=CUTOFF,
        policy_version="SIGNED-POLICY",
        approval_reference="policy approval fixture",
        max_modified_duration_years=Decimal("3"),
    )
    comparison = PortfolioScenarioEvidenceBridge.compare(
        _positions(),
        evidence.market_risks,
        {"A": Decimal("0.5"), "B": Decimal("0.5")},
        cutoff=CUTOFF,
        portfolio_market_value_crc=evidence.total_market_value_crc,
        portfolio_valuation_source=evidence.master_file,
        policy=policy,
    )
    assert comparison.current_credit_rwa_crc == Decimal("200")
    assert comparison.comparison.missing_limits == ("hqla", "dv01", "credit_rwa")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("market_value_crc", None, "unavailable"),
        ("market_value_crc", Decimal("NaN"), "finite"),
        ("source_currency", "", "currency"),
        ("classification", "", "classification"),
        ("principal_balance", None, "duration"),
        ("isin", "OTHER-ISIN", "ISIN"),
        ("issuer", "Wrong Issuer", "issuer"),
    ],
)
def test_missing_or_wrong_native_evidence_fails_closed(
    field: str, value: object, message: str
) -> None:
    master = _master()
    rows = list(master.normalized_positions)
    rows[1] = {**rows[1], field: value}
    with pytest.raises(ValueError, match=message):
        _adapt(master=replace(master, normalized_positions=rows))


def test_source_cutoff_row_mapping_and_native_crc_header_are_mandatory() -> None:
    with pytest.raises(ValueError, match="cutoff"):
        _adapt(master=replace(_master(), valuation_date=date(2026, 10, 1)))
    with pytest.raises(ValueError, match="completeness"):
        _adapt(master=replace(_master(), source_status="DEGRADED"))
    with pytest.raises(ValueError, match="unique"):
        _adapt(mapping={"A": 17, "B": 17})
    with pytest.raises(ValueError, match="Native institutional columns"):
        mapping = dict(_master().detected_column_mapping)
        mapping.pop("market_value_crc")
        _adapt(master=replace(_master(), detected_column_mapping=mapping))


def test_native_currency_requires_verified_not_reader_default() -> None:
    master = _master()
    positions = _positions()
    usd = replace(
        positions[0], currency="USD", fx_translation_source="verified fx source"
    )
    with pytest.raises(ValueError, match="currency"):
        _adapt(positions=(usd, positions[1]), master=master)


def test_missing_physical_master_path_has_no_demo_fallback(tmp_path) -> None:
    with pytest.raises(ValueError, match="unverified"):
        InstitutionalMasterScenarioRiskAdapter.read_file(
            tmp_path / "02-10-2026.xlsx",
            _positions(),
            {"A": 17, "B": 19},
            cutoff=CUTOFF,
        )


def test_read_file_requires_a_dated_unambiguous_name(monkeypatch) -> None:
    calls: list[date | None] = []

    def read_fake(self, path, *, valuation_date_override=None, diagnostic_mode=False):
        calls.append(valuation_date_override)
        return _master()

    monkeypatch.setattr(
        "aip.product.configured.adapters.institutional_portfolio_scenario_adapter."
        "InstitutionalPortfolioMasterReader.read",
        read_fake,
    )
    result = InstitutionalMasterScenarioRiskAdapter.read_file(
        "master-02-10-2026.xlsx",
        _positions(),
        {"A": 17, "B": 19},
        cutoff=CUTOFF,
    )
    assert result.total_market_value_crc == Decimal("1000")
    assert calls == [CUTOFF]

    with pytest.raises(ValueError, match="filename"):
        InstitutionalMasterScenarioRiskAdapter.read_file(
            "master-not-dated.xlsx",
            _positions(),
            {"A": 17, "B": 19},
            cutoff=CUTOFF,
        )
    with pytest.raises(ValueError, match="filename cutoff"):
        InstitutionalMasterScenarioRiskAdapter.read_file(
            "master-03-10-2026.xlsx",
            _positions(),
            {"A": 17, "B": 19},
            cutoff=CUTOFF,
        )
    assert calls == [CUTOFF]
