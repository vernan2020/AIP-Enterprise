"""Qt smoke tests for read-only contractual reconciliation in the real Liquidez UI."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QPushButton, QTabWidget, QTableWidget

from aip.ui.modules.liquidity.views.sugef210_projection_panel import SUGEF210ProjectionPanel


def test_contractual_tab_and_cutoff_invalidation_without_private_cash():
    app = QApplication.instance() or QApplication([])
    panel = SUGEF210ProjectionPanel()
    button = panel.findChild(QPushButton, "sugef210RunContractualReconciliation")
    table = panel.findChild(QTableWidget, "sugef210ContractualReconciliationDetail")
    tabs = panel.findChild(QTabWidget)
    assert app is not None
    assert button is not None and button.isEnabled()
    assert table is not None and tabs is not None
    cutoff = panel._cutoff
    panel._receive_contractual_audit(
        cutoff,
        {
            "status": "MATCHED_REFERENCE_ONLY",
            "cutoff": cutoff.isoformat(),
            "maturity_records": 20,
            "unique_maturity_rows_matched": 20,
            "principal_reconciliation": {
                "distinct_contracts_reconciled_exactly": 19,
                "negative_contracts_matching_signed_band_total": 1,
                "distinct_contracts_with_principal_difference": 0,
            },
            "contract_identities_without_maturity_bands_by_source": {
                "CAPTACIONES": 1,
                "BORROWING": 0,
            },
            "unbanded_date_evidence_by_sugef210_window": {
                "by_window": {"D01": 1},
                "next_day_concentration_review": {
                    "status": "NO_LARGE_NEXT_DAY_CLUSTER_DETECTED",
                    "next_day_unbanded_contracts": 1,
                    "future_dated_unbanded_contracts": 1,
                },
            },
        },
    )
    assert table.rowCount() == 22
    assert "SIN CERTIFICAR" in [
        table.item(row, 1).text() for row in range(table.rowCount())
    ]
    assert "privado" not in table.item(0, 2).text().lower()
    assert tabs.currentWidget() is table

    next_cutoff = date(cutoff.year - 1, cutoff.month, cutoff.day)
    panel._on_date_changed(QDate(next_cutoff.year, next_cutoff.month, next_cutoff.day))
    assert table.rowCount() == 0
    panel.close()
