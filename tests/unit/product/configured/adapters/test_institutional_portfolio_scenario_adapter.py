from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
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
    VerifiedScenarioFXRate,
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
            "market_value": value,
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
                "market_value",
                "currency",
                "issuer",
                "isin",
                "classification",
                "product_code",
                "principal_balance",
            )
        },
    )


def _adapt(master=None, positions=None, mapping=None, fx=None):
    return InstitutionalMasterScenarioRiskAdapter.adapt(
        _master() if master is None else master,
        _positions() if positions is None else positions,
        {"A": 17, "B": 19} if mapping is None else mapping,
        cutoff=CUTOFF,
        fx_rates_by_currency=fx,
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
        ("market_value", None, "unavailable"),
        ("market_value", 900, "reconciled"),
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
    usd = replace(positions[0], currency="USD", fx_translation_source="verified fx source")
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


def test_real_xlsx_reader_boundary_supplies_dated_native_risk_inputs(
    tmp_path: Path,
) -> None:
    path = tmp_path / "02-10-2026.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Cartera"
    sheet.append(
        [
            "#",
            "Emisor",
            "Moneda",
            "Código Producto",
            "Clasificación",
            "Valor Mercado Colonizado",
            "ISIN",
            "Saldo Principal",
            "Saldo Valor Mercado",
            "Saldo Valor Compra",
            "Tasa Nominal",
            "Periodicidad",
            "TIR",
            "Fecha Vencimiento",
        ]
    )
    for serial, issuer, classification, market, isin in (
        (1, "G", "D.V GOBIERNO", 600, "TEST-A"),
        (2, "Issuer B", "PRIVADA", 400, "TEST-B"),
    ):
        sheet.append(
            [
                serial,
                issuer,
                "CRC",
                "BONO",
                classification,
                market,
                isin,
                market,
                market,
                market,
                5,
                "semestral",
                5.5,
                date(2028, 10, 2),
            ]
        )
    workbook.save(path)
    workbook.close()

    evidence = InstitutionalMasterScenarioRiskAdapter.read_file(
        path,
        _positions(),
        {"A": 2, "B": 3},
        cutoff=CUTOFF,
    )
    assert evidence.total_market_value_crc == Decimal("1000")
    assert tuple(row.position_key for row in evidence.market_risks) == ("A", "B")
    assert evidence.market_risks[0].eligible_hqla_value_crc == Decimal("540.00")
    assert evidence.market_risks[1].dv01_crc > 0
    assert "row:2" in evidence.market_risks[0].market_value_source


def test_foreign_master_needs_approved_matching_historical_fx() -> None:
    positions = _positions()
    usd = replace(
        positions[1],
        currency="USD",
        exposure_class=ExposureClass.GOVERNMENT_USD,
        fx_translation_source="BCCR-SELL-2026-10-02",
    )
    master = _master()
    rows = list(master.normalized_positions)
    rows[0] = {
        **rows[0],
        "source_currency": "USD",
        "currency": "USD",
        "market_value": Decimal("2"),
        "market_value_crc": Decimal("900"),
    }
    fx = VerifiedScenarioFXRate(
        currency="USD",
        cutoff=CUTOFF,
        effective_date=CUTOFF,
        crc_per_unit=Decimal("450"),
        rate_type="BCCR_SELL",
        source_reference="BCCR-SELL-2026-10-02",
    )
    audited_rows = (positions[0], usd)
    with pytest.raises(ValueError, match="explicit approved FX"):
        _adapt(master=replace(master, normalized_positions=rows), positions=audited_rows)
    result = _adapt(
        master=replace(master, normalized_positions=rows),
        positions=audited_rows,
        fx={"USD": fx},
    )
    assert result.total_market_value_crc == Decimal("1500")
    assert "BCCR-SELL-2026-10-02" in result.market_risks[1].market_value_source
    with pytest.raises(ValueError, match="reconciled"):
        _adapt(
            master=replace(master, normalized_positions=rows),
            positions=audited_rows,
            fx={"USD": replace(fx, crc_per_unit=Decimal("449"))},
        )
    with pytest.raises(ValueError, match="provenance"):
        _adapt(
            master=replace(master, normalized_positions=rows),
            positions=audited_rows,
            fx={"USD": replace(fx, source_reference="OTHER-APPROVED-RATE")},
        )
    with pytest.raises(ValueError, match="provenance"):
        _adapt(
            master=replace(master, normalized_positions=rows),
            positions=audited_rows,
            fx={"USD": replace(fx, effective_date=date(2026, 10, 3))},
        )


def test_crc_positions_reject_hidden_currency_conversion() -> None:
    master = _master()
    rows = list(master.normalized_positions)
    rows[0] = {**rows[0], "market_value": Decimal("200")}
    with pytest.raises(ValueError, match="reconciled"):
        _adapt(master=replace(master, normalized_positions=rows))
