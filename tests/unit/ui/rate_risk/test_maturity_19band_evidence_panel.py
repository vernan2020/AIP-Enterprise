from __future__ import annotations

from datetime import date

from aip.ui.modules.rate_risk.views.maturity_19band_evidence_panel import (
    Maturity19BandEvidencePanel,
)
from aip.ui.modules.rate_risk.views.rate_risk_workspace import RateRiskWorkspace


def _evidence() -> dict[str, object]:
    return {
        "source_records": 3,
        "observed_records": 1,
        "excluded_records": 2,
        "currency_reconciliation": [
            {
                "currency_code": "1",
                "source_valid_principal": "2134.50",
                "assigned_principal": "1234.50",
                "excluded_valid_principal": "900",
                "invalid_principal_records": 0,
                "status": "RECONCILED_VALID_PRINCIPAL",
            }
        ],
        "term_rate_review": [
            {
                "currency_code": "1",
                "rate_type_source_code": "V",
                "maturity_quality": "CURRENT_OR_FUTURE_MATURITY",
                "records": 2,
                "valid_source_principal": "900",
            }
        ],
        "bands": [
            {
                "currency_code": "1",
                "ordinal": 2,
                "band": "1 día a 1 mes",
                "records": 1,
                "source_principal": "1234.50",
            }
        ],
        "excluded": [
            {
                "currency_code": "1",
                "reason": "SIGHT_NMD_BEHAVIORAL_PROFILE_REQUIRED",
                "records": 2,
                "source_principal": "900",
            }
        ],
    }


def test_panel_displays_maturity_only_and_unassigned_categories(qt_app) -> None:
    panel = Maturity19BandEvidencePanel()
    try:
        cutoff = date(2026, 9, 30)
        panel.set_cutoff(cutoff)
        panel._receive_result(cutoff, _evidence())
        assert panel._bands.rowCount() == 1
        assert panel._excluded.rowCount() == 1
        assert panel._reconciliation.rowCount() == 1
        assert panel._reconciliation.item(0, 1).text() == "2.134,50"
        assert panel._rate_review.rowCount() == 1
        assert panel._rate_review.item(0, 1).text() == "V"
        assert panel._rate_review.item(0, 4).text() == "900"
        assert panel._bands.item(0, 1).text() == "2. 1 día a 1 mes"
        assert panel._bands.item(0, 3).text() == "1.234,50"
        assert "A la vista" in panel._excluded.item(0, 1).text()
        assert "SIGHT_NMD" in panel._excluded.item(0, 1).toolTip()
        assert "NO certificado RTILB" in panel._status.text()
    finally:
        panel.close()


def test_panel_does_not_reuse_stale_cutoff_results(qt_app) -> None:
    panel = Maturity19BandEvidencePanel()
    try:
        panel.set_cutoff(date(2026, 9, 30))
        panel._receive_result(date(2026, 9, 30), _evidence())
        panel.set_cutoff(date(2026, 10, 15))
        panel._receive_result(date(2026, 9, 30), _evidence())
        assert panel._bands.rowCount() == 0
        assert panel._excluded.rowCount() == 0
        assert panel._reconciliation.rowCount() == 0
        assert panel._rate_review.rowCount() == 0
        assert "15/10/2026" in panel._status.text()
    finally:
        panel.close()


def test_workspace_has_separate_evidence_and_certified_gap_tabs(qt_app) -> None:
    workspace = RateRiskWorkspace(
        valuation_date_provider=lambda: date(2026, 9, 30), controller=None
    )
    try:
        labels = [workspace.view._tabs.tabText(i) for i in range(workspace.view._tabs.count())]
        assert "Bandeo 19 · evidencia" in labels
        assert "GAP SUGEF · 19 bandas" in labels
        assert all(value.text() == "N/D" for value in workspace.view._kpi_values.values())
    finally:
        workspace.close()
