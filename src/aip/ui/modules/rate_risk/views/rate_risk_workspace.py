from __future__ import annotations

from collections.abc import Callable
from datetime import date

from PySide6.QtWidgets import QVBoxLayout, QWidget

from aip.product.configured.irrbb.regulatory_financial_xml import RegulatoryFinancialXMLReader
from aip.product.configured.irrbb.regulatory_gap_six_band import build_regulatory_gap
from aip.ui.modules.rate_risk.controllers import RateRiskWorkspaceController
from aip.ui.modules.rate_risk.views.contractual_exposure_panel import ContractualExposurePanel
from aip.ui.modules.rate_risk.views.investment_master_evidence_panel import (
    InvestmentMasterEvidencePanel,
)
from aip.ui.modules.rate_risk.views.maturity_19band_evidence_panel import (
    Maturity19BandEvidencePanel,
)
from aip.ui.modules.rate_risk.views.regulatory_xml_panel import RegulatoryXMLPanel
from aip.ui.modules.rate_risk.views.source_diagnostics_rate_risk_view import RateRiskView


class RateRiskWorkspace(QWidget):
    """UI coordinator for the passive RTILB view and application controller.

    Refreshing this widget reloads the immutable read-model for the active global
    cutoff. When the configured runtime is absent, the view remains explicitly in
    its UNCONFIGURED state and no financial values are synthesized.
    """

    def __init__(
        self,
        *,
        valuation_date_provider: Callable[[], date],
        controller: RateRiskWorkspaceController | None = None,
        regulatory_xml_reader: RegulatoryFinancialXMLReader | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("rateRiskWorkspaceHost")
        self._valuation_date_provider = valuation_date_provider
        self._controller = controller
        self._view = RateRiskView()
        self._regulatory_xml_reader = regulatory_xml_reader
        self._regulatory_xml_panel = RegulatoryXMLPanel()
        self._view._tabs.addTab(self._regulatory_xml_panel, "XML Brechas / Calce")
        self._contractual_exposure_panel = ContractualExposurePanel()
        self._view._tabs.addTab(self._contractual_exposure_panel, "XML contractual · auditoría")
        self._maturity_evidence_panel = Maturity19BandEvidencePanel()
        self._view._tabs.addTab(self._maturity_evidence_panel, "Bandeo 19 · evidencia")
        self._investment_master_panel = InvestmentMasterEvidencePanel()
        self._view._tabs.addTab(self._investment_master_panel, "Inversiones · Maestro")
        self._view._open_regulatory_evidence.setEnabled(True)
        self._view._open_regulatory_evidence.clicked.connect(
            lambda: self._view._tabs.setCurrentWidget(self._regulatory_xml_panel)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view)

        self.refresh()

    @property
    def view(self) -> RateRiskView:
        return self._view

    @property
    def is_configured(self) -> bool:
        return self._controller is not None

    def refresh(self) -> None:
        cutoff_date = self._valuation_date_provider()
        self._contractual_exposure_panel.set_cutoff(cutoff_date)
        self._maturity_evidence_panel.set_cutoff(cutoff_date)
        self._investment_master_panel.set_cutoff(cutoff_date)
        if self._regulatory_xml_reader is None:
            self._regulatory_xml_panel.set_unconfigured()
            self._view.set_regulatory_evidence_status(
                "XML Brechas / Calce: fuente regulatoria no configurada. "
                "No se asumen saldos ni flujos."
            )
        else:
            snapshot = self._regulatory_xml_reader.load_latest(reference_cutoff=cutoff_date)
            self._regulatory_xml_panel.set_snapshot(snapshot, valuation_cutoff=cutoff_date)
            regulatory_gap = build_regulatory_gap(snapshot)
            if snapshot.is_valid and regulatory_gap.is_ready:
                rows = {item.key: len(item.rows) for item in snapshot.files}
                same_month = (
                    snapshot.cutoff_date.year,
                    snapshot.cutoff_date.month,
                ) == (cutoff_date.year, cutoff_date.month)
                headline = (
                    f"XML Brechas / Calce {snapshot.cutoff_date:%m/%Y} conciliados · "
                    f"{rows.get('BRECHAS', 0)} Brechas + "
                    f"{rows.get('CALCE', 0)} Calce · "
                    "GAP regulatorio de 6 bandas disponible. "
                )
                if same_month:
                    headline += "ΔNII/ΔVEP requieren cálculo contractual independiente."
                else:
                    headline += (
                        f"Desfase con corte AIP {cutoff_date:%m/%Y}: "
                        "solo evidencia histórica, no cálculo RTILB vigente."
                    )
                self._view.set_regulatory_evidence_status(
                    headline, status="ready" if same_month else "stale"
                )
            else:
                if snapshot.is_valid:
                    issue = next(
                        iter(regulatory_gap.issues),
                        "Faltan las seis bandas del GAP regulatorio.",
                    )
                    prefix = "XML estructuralmente validados; GAP de 6 bandas bloqueado"
                else:
                    issue = next(
                        (problem for item in snapshot.files for problem in item.issues),
                        "Falta el par XML válido.",
                    )
                    prefix = "XML Brechas / Calce no validados"
                self._view.set_regulatory_evidence_status(
                    f"{prefix}: {issue} No se muestran importes no certificados.",
                    status="blocked",
                )
        controller = self._controller
        if controller is None:
            self._view.set_read_model(None)
            return

        self._view.set_read_model(controller.load(cutoff_date=cutoff_date))
