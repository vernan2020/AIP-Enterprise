from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.irrbb.regulatory_financial_xml import (
    RegulatoryXMLFileResult,
    RegulatoryXMLPairResult,
    RegulatoryXMLRow,
)
from aip.product.configured.irrbb.regulatory_gap_six_band import build_regulatory_gap


def _snapshot(*, missing: tuple[str, str] | None = None, mismatch: bool = False):
    rows = []
    values = {
        "22110": 100,
        "22210": 50,
        "22310": 150,
        "22120": 70,
        "22220": 20,
        "22320": 90,
    }
    for band in range(1, 7):
        for account, amount in values.items():
            if missing == (account, str(band)):
                continue
            actual = amount + 1 if mismatch and band == 4 and account == "22310" else amount
            rows.append(
                RegulatoryXMLRow(
                    str(len(rows) + 1),
                    account,
                    "5",
                    str(band),
                    Decimal(actual),
                )
            )
    return RegulatoryXMLPairResult(
        date(2026, 9, 30),
        (
            RegulatoryXMLFileResult(
                "BRECHAS",
                "Contable_Brecha.xml",
                "VALIDATED",
                rows=tuple(rows),
            ),
            RegulatoryXMLFileResult(
                "CALCE",
                "Contable_CalcePlazo.xml",
                "VALIDATED",
            ),
        ),
    )


def test_six_band_gap_uses_only_official_assets_and_liabilities_parents():
    result = build_regulatory_gap(_snapshot())
    assert result.is_ready
    assert len(result.rows) == 6
    assert [line.bucket_code for line in result.rows] == ["1", "2", "3", "4", "5", "6"]
    assert result.rows[0].assets_crc == Decimal("150")
    assert result.rows[0].liabilities_crc == Decimal("90")
    assert result.rows[0].gap_crc == Decimal("60")
    assert result.rows[-1].cumulative_gap_crc == Decimal("360")


def test_missing_parent_or_component_never_becomes_an_inferred_zero():
    result = build_regulatory_gap(_snapshot(missing=("22220", "6")))
    assert not result.is_ready
    assert result.rows == ()
    assert "Banda 6" in result.issues[0]


def test_mother_account_inconsistent_with_mn_me_blocks_entire_gap():
    result = build_regulatory_gap(_snapshot(mismatch=True))
    assert not result.is_ready
    assert result.rows == ()
    assert any("activos" in issue for issue in result.issues)


def test_blocked_input_does_not_create_an_aggregate_gap():
    source = _snapshot()
    blocked = RegulatoryXMLPairResult(
        source.cutoff_date,
        (
            source.files[0],
            RegulatoryXMLFileResult("CALCE", "Contable_CalcePlazo.xml", "BLOCKED"),
        ),
    )
    result = build_regulatory_gap(blocked)
    assert result.status == "BLOCKED"
    assert result.rows == ()
