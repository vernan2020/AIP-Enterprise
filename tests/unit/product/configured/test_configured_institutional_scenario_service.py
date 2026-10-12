from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aip.domain.portfolio.services.portfolio_capital_consumption_service import (
    ExposureClass,
)
from aip.domain.portfolio.services.portfolio_capital_evidence_service import (
    VerifiedCapitalPosition,
)
from aip.domain.portfolio.services.portfolio_scenario_evidence_bridge import (
    VerifiedPositionMarketRisk,
)
from aip.domain.portfolio.services.portfolio_scenario_risk_service import ScenarioRiskPolicy
from aip.product.configured.adapters.institutional_portfolio_scenario_adapter import (
    InstitutionalScenarioMarketEvidence,
    VerifiedScenarioFXRate,
)
from aip.product.configured.services.configured_institutional_scenario_service import (
    ApprovedMasterAttestation,
    ConfiguredInstitutionalScenarioService,
)

CUTOFF = date(2026, 10, 2)


@dataclass
class _Provider:
    payload: dict[str, Any]

    def get_portfolio(self) -> dict[str, Any]:
        return self.payload


def _snapshot(directory: str, **changes: Any) -> dict[str, Any]:
    snapshot = {
        "data_quality_status": "HEALTHY",
        "valuation_date": CUTOFF.isoformat(),
        "portfolio_master": {
            "status": "HEALTHY",
            "valuation_date": CUTOFF.isoformat(),
            "directory": directory,
            "file_name": "02-10-2026.xlsx",
        },
    }
    snapshot.update(changes)
    return snapshot


def _capital() -> tuple[VerifiedCapitalPosition, ...]:
    return tuple(
        VerifiedCapitalPosition(
            position_key=key,
            isin=f"ISIN-{key}",
            issuer=f"Issuer {key}",
            currency="CRC",
            cutoff=CUTOFF,
            invested_amount_crc=Decimal("100"),
            regulatory_exposure_crc=Decimal("50"),
            annual_net_yield=Decimal("0.05"),
            exposure_class=ExposureClass.UNRATED,
            classification_effective_date=CUTOFF,
            invested_amount_source="acquisition evidence fixture",
            regulatory_exposure_source="regulatory exposure fixture",
            net_yield_source="net income fixture",
            classification_source="classification fixture",
        )
        for key in ("A", "B")
    )


def _market() -> tuple[VerifiedPositionMarketRisk, ...]:
    return tuple(
        VerifiedPositionMarketRisk(
            position_key=key,
            cutoff=CUTOFF,
            market_value_crc=Decimal("100"),
            modified_duration_years=Decimal("2"),
            dv01_crc=Decimal("0.02"),
            eligible_hqla_value_crc=Decimal("90"),
            market_value_source="master native CRC fixture",
            duration_source="duration engine fixture",
            dv01_source="DV01 engine fixture",
            hqla_source="HQLA engine fixture",
        )
        for key in ("A", "B")
    )


def _policy() -> ScenarioRiskPolicy:
    return ScenarioRiskPolicy(
        cutoff=CUTOFF,
        effective_date=CUTOFF,
        policy_version="SIGNED-TEST",
        approval_reference="signed investment policy fixture",
        max_modified_duration_years=Decimal("3"),
    )


def test_uses_exact_configured_master_and_reconciles_before_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoked: list[Path] = []

    def fake_read(cls, master_file, positions, row_ids, *, cutoff, fx_rates_by_currency):
        invoked.append(Path(master_file))
        assert tuple(row.position_key for row in positions) == ("A", "B")
        assert row_ids == {"A": 17, "B": 19}
        assert cutoff == CUTOFF
        assert fx_rates_by_currency is None
        return InstitutionalScenarioMarketEvidence(
            cutoff=CUTOFF,
            master_file=str(master_file),
            sheet_name="Master",
            market_risks=_market(),
            total_market_value_crc=Decimal("200"),
        )

    monkeypatch.setattr(
        "aip.product.configured.services.configured_institutional_scenario_service."
        "InstitutionalMasterScenarioRiskAdapter.read_file",
        classmethod(fake_read),
    )
    service = ConfiguredInstitutionalScenarioService(_Provider(_snapshot(str(tmp_path))))
    outcome = service.evaluate(
        _capital(),
        {"A": 17, "B": 19},
        {"A": Decimal("0.6"), "B": Decimal("0.4")},
        cutoff=CUTOFF,
        policy=_policy(),
    )
    assert invoked == [tmp_path / "02-10-2026.xlsx"]
    assert outcome.current_credit_rwa_crc == Decimal("100")
    assert outcome.comparison.current.modified_duration_years == Decimal("2")
    assert outcome.comparison.proposed.status == "INCOMPLETE"
    assert "hqla" in outcome.comparison.missing_limits


@pytest.mark.parametrize(
    ("update", "message"),
    [
        ({"data_quality_status": "DEGRADED"}, "quality"),
        ({"valuation_date": "2026-10-01"}, "cutoff"),
        ({"portfolio_master": {"status": "DEGRADED"}}, "verified source"),
        (
            {
                "portfolio_master": {
                    "status": "HEALTHY",
                    "valuation_date": "2026-10-01",
                }
            },
            "date",
        ),
    ],
)
def test_fails_closed_before_file_access(update: dict, message: str, tmp_path: Path) -> None:
    provider = _Provider(_snapshot(str(tmp_path), **update))
    with pytest.raises(ValueError, match=message):
        ConfiguredInstitutionalScenarioService(provider).evaluate(
            _capital(),
            {"A": 17, "B": 19},
            {"A": Decimal("0.5"), "B": Decimal("0.5")},
            cutoff=CUTOFF,
            policy=_policy(),
        )


@pytest.mark.parametrize("filename", ("../outside.xlsx", r"other\\file.xlsx", "unsafe.csv", ""))
def test_untrusted_source_filename_is_rejected(tmp_path: Path, filename: str) -> None:
    snapshot = _snapshot(str(tmp_path))
    snapshot["portfolio_master"]["file_name"] = filename
    with pytest.raises(ValueError, match="filename"):
        ConfiguredInstitutionalScenarioService(_Provider(snapshot)).evaluate(
            _capital(),
            {"A": 17, "B": 19},
            {"A": Decimal("0.5"), "B": Decimal("0.5")},
            cutoff=CUTOFF,
            policy=_policy(),
        )


def test_configured_service_propagates_explicit_approved_fx_to_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rate = VerifiedScenarioFXRate(
        currency="USD",
        cutoff=CUTOFF,
        effective_date=CUTOFF,
        crc_per_unit=Decimal("450"),
        rate_type="BCCR_SELL",
        source_reference="BCCR-SELL-2026-10-02",
    )
    checked: list[dict[str, VerifiedScenarioFXRate]] = []

    def fake_read(cls, master_file, positions, row_ids, *, cutoff, fx_rates_by_currency):
        assert cutoff == CUTOFF
        assert positions[1].fx_translation_source == rate.source_reference
        checked.append(dict(fx_rates_by_currency))
        return InstitutionalScenarioMarketEvidence(
            cutoff=CUTOFF,
            master_file=str(master_file),
            sheet_name="Master",
            market_risks=_market(),
            total_market_value_crc=Decimal("200"),
        )

    monkeypatch.setattr(
        "aip.product.configured.services.configured_institutional_scenario_service."
        "InstitutionalMasterScenarioRiskAdapter.read_file",
        classmethod(fake_read),
    )
    base_positions = _capital()
    positions = (
        base_positions[0],
        replace(
            base_positions[1],
            currency="USD",
            fx_translation_source=rate.source_reference,
        ),
    )
    output = ConfiguredInstitutionalScenarioService(_Provider(_snapshot(str(tmp_path)))).evaluate(
        positions,
        {"A": 17, "B": 19},
        {"A": Decimal("0.6"), "B": Decimal("0.4")},
        cutoff=CUTOFF,
        policy=_policy(),
        fx_rates_by_currency={"USD": rate},
    )
    assert checked == [{"USD": rate}]
    assert output.comparison.current.status == "INCOMPLETE"


def test_declared_master_manifest_must_match_file_digest_and_sheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = "a" * 64

    def read_fixture(cls, master_file, positions, row_ids, *, cutoff, fx_rates_by_currency):
        return InstitutionalScenarioMarketEvidence(
            cutoff=CUTOFF,
            master_file=str(master_file),
            sheet_name="Cartera",
            market_risks=_market(),
            total_market_value_crc=Decimal("200"),
            master_sha256=digest,
        )

    monkeypatch.setattr(
        "aip.product.configured.services.configured_institutional_scenario_service."
        "InstitutionalMasterScenarioRiskAdapter.read_file",
        classmethod(read_fixture),
    )
    path = tmp_path / "02-10-2026.xlsx"
    approved = ApprovedMasterAttestation(
        cutoff=CUTOFF,
        master_file=str(path),
        sheet_name="Cartera",
        sha256=digest,
        approval_reference="approved-external-register-fixture",
    )
    service = ConfiguredInstitutionalScenarioService(_Provider(_snapshot(str(tmp_path))))

    def evaluate(attestation):
        return service.evaluate(
            _capital(),
            {"A": 17, "B": 19},
            {"A": Decimal("0.6"), "B": Decimal("0.4")},
            cutoff=CUTOFF,
            policy=_policy(),
            master_attestation=attestation,
        )

    result = evaluate(approved)
    assert "|manifest-match:approved-external-register-fixture" in (
        result.portfolio_valuation_source
    )
    assert evaluate(None).portfolio_valuation_source.endswith("|manifest-not-supplied")
    with pytest.raises(ValueError, match="digest or sheet"):
        evaluate(replace(approved, sha256="b" * 64))
    with pytest.raises(ValueError, match="digest or sheet"):
        evaluate(replace(approved, sheet_name="Otra hoja"))
    with pytest.raises(ValueError, match="invalid"):
        evaluate(replace(approved, cutoff=date(2026, 10, 1)))
    with pytest.raises(ValueError, match="invalid"):
        evaluate(replace(approved, master_file=str(tmp_path / "other.xlsx")))
    with pytest.raises(ValueError, match="invalid"):
        evaluate(replace(approved, sha256="non-hex-or-short"))
    with pytest.raises(ValueError, match="invalid"):
        evaluate(replace(approved, approval_reference=""))


def test_selected_master_cannot_escape_configured_folder_via_symlink(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "approved"
    allowed.mkdir()
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"unapproved master")
    (allowed / "02-10-2026.xlsx").symlink_to(outside)
    service = ConfiguredInstitutionalScenarioService(_Provider(_snapshot(str(allowed))))
    with pytest.raises(ValueError, match="regular file inside"):
        service.evaluate(
            _capital(),
            {"A": 17, "B": 19},
            {"A": Decimal("0.5"), "B": Decimal("0.5")},
            cutoff=CUTOFF,
            policy=_policy(),
        )
