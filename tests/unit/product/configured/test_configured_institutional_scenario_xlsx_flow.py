from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import ExposureClass
from aip.domain.portfolio.services.portfolio_capital_evidence_service import VerifiedCapitalPosition
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy
from aip.product.configured.adapters.institutional_portfolio_scenario_adapter import (
    VerifiedScenarioFXRate,
)
from aip.product.configured.services.configured_institutional_scenario_service import (
    ConfiguredInstitutionalScenarioService,
)

CUTOFF = date(2026, 10, 2)


class _Source:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get_portfolio(self) -> dict:
        return {
            "valuation_date": CUTOFF.isoformat(),
            "data_quality_status": "HEALTHY",
            "portfolio_master": {
                "status": "HEALTHY",
                "valuation_date": CUTOFF.isoformat(),
                "directory": str(self._directory),
                "file_name": "02-10-2026.xlsx",
            },
        }


def _write_master(directory: Path) -> Path:
    path = directory / "02-10-2026.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Maestro"
    sheet.append(
        [
            "#",
            "Emisor",
            "Número Contrato",
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
    sheet.append(
        [
            1,
            "G",
            "CTR-A",
            "CRC",
            "BONO",
            "D.V GOBIERNO",
            600,
            "TEST-A",
            600,
            600,
            580,
            5,
            "semestral",
            5.5,
            date(2028, 10, 2),
        ]
    )
    sheet.append(
        [
            2,
            "Issuer B",
            "CTR-B",
            "USD",
            "BONO",
            "PRIVADA",
            900,
            "TEST-B",
            2,
            2,
            1.9,
            5,
            "semestral",
            5.5,
            date(2028, 10, 2),
        ]
    )
    workbook.save(path)
    workbook.close()
    return path


def _capital() -> tuple[VerifiedCapitalPosition, ...]:
    def row(
        key: str,
        isin: str,
        issuer: str,
        currency: str,
        exposure: str,
        cls: ExposureClass,
        fx_source: str = "",
    ) -> VerifiedCapitalPosition:
        return VerifiedCapitalPosition(
            position_key=key,
            isin=isin,
            issuer=issuer,
            currency=currency,
            cutoff=CUTOFF,
            invested_amount_crc=Decimal("500"),
            regulatory_exposure_crc=Decimal(exposure),
            annual_net_yield=Decimal("0.05"),
            exposure_class=cls,
            classification_effective_date=CUTOFF,
            invested_amount_source="audited acquisition fixture",
            regulatory_exposure_source="audited APR basis fixture",
            net_yield_source="audited yield fixture",
            classification_source="approved bucket fixture",
            fx_translation_source=fx_source,
        )

    return (
        row(
            "contract:CTR-A|isin:TEST-A",
            "TEST-A",
            "G",
            "CRC",
            "500",
            ExposureClass.GOVERNMENT_CRC,
        ),
        row(
            "contract:CTR-B|isin:TEST-B",
            "TEST-B",
            "Issuer B",
            "USD",
            "120",
            ExposureClass.UNRATED,
            "BCCR-SELL-CUTOFF",
        ),
    )


def _policy() -> ScenarioRiskPolicy:
    return ScenarioRiskPolicy(
        cutoff=CUTOFF,
        effective_date=CUTOFF,
        policy_version="SIGNED-2026-TEST",
        approval_reference="approved policy fixture",
        max_modified_duration_years=Decimal("10"),
        min_hqla_fraction=Decimal("0.5"),
    )


def _fx(rate: str = "450") -> dict[str, VerifiedScenarioFXRate]:
    return {
        "USD": VerifiedScenarioFXRate(
            currency="USD",
            cutoff=CUTOFF,
            effective_date=CUTOFF,
            crc_per_unit=Decimal(rate),
            rate_type="BCCR_SELL",
            source_reference="BCCR-SELL-CUTOFF",
        )
    }


def test_complete_real_reader_to_fx_capital_policy_scenario(
    tmp_path: Path,
) -> None:
    master = _write_master(tmp_path)
    outcome = ConfiguredInstitutionalScenarioService(_Source(tmp_path)).evaluate(
        _capital(),
        None,  # contract + ISIN identity is derived from native headers
        {
            "contract:CTR-A|isin:TEST-A": Decimal("0.7"),
            "contract:CTR-B|isin:TEST-B": Decimal("0.3"),
        },
        cutoff=CUTOFF,
        policy=_policy(),
        fx_rates_by_currency=_fx(),
    )

    assert outcome.position_keys == (
        "contract:CTR-A|isin:TEST-A",
        "contract:CTR-B|isin:TEST-B",
    )
    assert outcome.portfolio_valuation_source == (
        f"{master}|sha256:{hashlib.sha256(master.read_bytes()).hexdigest()}"
        "|manifest-not-supplied"
    )
    assert outcome.comparison.portfolio_value_crc == Decimal("1500")
    assert outcome.regulatory_exposure_crc == Decimal("620")
    assert outcome.current_credit_rwa_crc == Decimal("120")
    assert outcome.comparison.current.credit_rwa_crc == Decimal("120")
    assert outcome.comparison.proposed.credit_rwa_crc.quantize(Decimal("0.01")) == Decimal("60.00")
    assert outcome.comparison.current.hqla_fraction == Decimal("0.36")
    assert outcome.comparison.proposed.hqla_fraction == Decimal("0.63")
    assert outcome.comparison.current.status == "BREACH"
    assert outcome.comparison.proposed.status == "INCOMPLETE"
    assert outcome.comparison.missing_limits == ("dv01", "credit_rwa")


def test_actual_xlsx_conversion_must_match_approved_rate(
    tmp_path: Path,
) -> None:
    _write_master(tmp_path)
    with pytest.raises(ValueError, match="reconciled"):
        ConfiguredInstitutionalScenarioService(_Source(tmp_path)).evaluate(
            _capital(),
            None,
            {
                "contract:CTR-A|isin:TEST-A": Decimal("0.7"),
                "contract:CTR-B|isin:TEST-B": Decimal("0.3"),
            },
            cutoff=CUTOFF,
            policy=_policy(),
            fx_rates_by_currency=_fx("451"),
        )
