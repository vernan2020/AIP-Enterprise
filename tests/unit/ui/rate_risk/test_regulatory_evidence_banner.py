from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aip.product.configured.irrbb.regulatory_financial_xml import (
    RegulatoryXMLFileResult,
    RegulatoryXMLPairResult,
    RegulatoryXMLRow,
)
from aip.ui.modules.rate_risk.views.rate_risk_workspace import RateRiskWorkspace


class _Source:
    def __init__(self, snapshot: RegulatoryXMLPairResult) -> None:
        self.snapshot = snapshot

    def load_latest(self, *, reference_cutoff: date) -> RegulatoryXMLPairResult:
        assert isinstance(reference_cutoff, date)
        return self.snapshot


def _pair(*, complete: bool) -> RegulatoryXMLPairResult:
    values = {
        "22110": 100,
        "22210": 50,
        "22310": 150,
        "22120": 70,
        "22220": 20,
        "22320": 90,
        "22300": 60,
    }
    rows = tuple(
        RegulatoryXMLRow(
            record_id=str(index + 1),
            account_code=account,
            catalog_code="5",
            bucket_code=str(band),
            amount=Decimal(amount),
        )
        for index, (band, account, amount) in enumerate(
            (band, account, amount)
            for band in range(1, 7)
            for account, amount in values.items()
        )
        if complete or band == 1
    )
    return RegulatoryXMLPairResult(
        cutoff_date=date(2026, 9, 1),
        files=(
            RegulatoryXMLFileResult(
                key="BRECHAS",
                filename="Contable_Brecha.xml",
                status="VALIDATED",
                period=date(2026, 9, 1),
                rows=rows,
            ),
            RegulatoryXMLFileResult(
                key="CALCE",
                filename="Contable_CalcePlazo.xml",
                status="VALIDATED",
                period=date(2026, 9, 1),
                rows=(),
            ),
        ),
    )


@pytest.mark.parametrize(
    ("cutoff", "expected", "banner_color"),
    [
        (date(2026, 9, 30), "ΔNII/ΔVEP requieren", "#EDF8F1"),
        (date(2026, 10, 15), "Desfase con corte AIP 10/2026", "#FFF8E7"),
    ],
)
def test_regulatory_banner_shows_independent_data_and_real_xml_navigation(
    qt_app, cutoff: date, expected: str, banner_color: str
) -> None:
    workspace = RateRiskWorkspace(
        valuation_date_provider=lambda: cutoff,
        controller=None,
        regulatory_xml_reader=_Source(_pair(complete=True)),
    )
    try:
        label = workspace.view._regulatory_evidence_label
        assert "XML Brechas / Calce 09/2026 conciliados" in label.text()
        assert "42 Brechas + 0 Calce" in label.text()
        assert "GAP regulatorio de 6 bandas disponible" in label.text()
        assert expected in label.text()
        assert banner_color in workspace.view._regulatory_evidence_banner.styleSheet()
        assert workspace.view._analysis_status_label.text() == "Estado: Sin cálculo"
        assert all(value.text() == "N/D" for value in workspace.view._kpi_values.values())
        assert workspace.view._tabs.currentIndex() == 0
        workspace.view._open_regulatory_evidence.click()
        assert workspace.view._tabs.currentWidget() is workspace._regulatory_xml_panel
        assert workspace._regulatory_xml_panel._gap_table.rowCount() == 6
    finally:
        workspace.close()


def test_regulatory_banner_does_not_claim_six_band_gap_from_partial_file(qt_app) -> None:
    workspace = RateRiskWorkspace(
        valuation_date_provider=lambda: date(2026, 9, 30),
        regulatory_xml_reader=_Source(_pair(complete=False)),
    )
    try:
        assert "XML estructuralmente validados" in workspace.view._regulatory_evidence_label.text()
        assert "GAP de 6 bandas bloqueado" in workspace.view._regulatory_evidence_label.text()
        assert workspace._regulatory_xml_panel._gap_table.rowCount() == 0
        assert all(value.text() == "N/D" for value in workspace.view._kpi_values.values())
    finally:
        workspace.close()
