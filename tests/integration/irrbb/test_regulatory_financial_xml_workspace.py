from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication

from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
    XMLConfiaSourceConfig,
)
from aip.product.configured.irrbb.regulatory_financial_xml import REGULATORY_XML_SPECS
from aip.product.demo.bootstrap.application_factory import DemoApplicationFactory
from aip.product.demo.configuration.demo_config import DemoConfig
from aip.ui.modules.rate_risk.views import RateRiskWorkspace
from aip.ui.shell.intelligence_main_window import FinancialIntelligenceMainWindow


def _xml(spec) -> str:
    return f"""<ArchivoSICVECA>
  <Encabezado>
    <ClaseDato>22</ClaseDato><Archivo>2201</Archivo>
    <Periodo>01/09/2026</Periodo><IdEntidad>3004045138</IdEntidad>
    <TipoCarga>1</TipoCarga><TipoMoneda>1</TipoMoneda>
  </Encabezado>
  <Datos>
    <Registro id="1" accion="insertar">
      <{spec.account_field}>101</{spec.account_field}>
      <TipoCatalogoSUGEF>{spec.catalog_code}</TipoCatalogoSUGEF>
      <{spec.bucket_field}>1</{spec.bucket_field}>
      <{spec.amount_field}>125</{spec.amount_field}>
    </Registro>
    <RegistroTotal id="1" accion="insertar">
      <{spec.account_field}>101</{spec.account_field}>
      <TipoCatalogoSUGEF>{spec.catalog_code}</TipoCatalogoSUGEF>
      <{spec.total_field}>125</{spec.total_field}>
    </RegistroTotal>
  </Datos>
</ArchivoSICVECA>
"""


def test_configured_shell_reads_regulatory_xml_without_enabling_eve(
    tmp_path: Path,
) -> None:
    month = tmp_path / "2026" / "09-SEPTIEMBRE"
    month.mkdir(parents=True)
    for spec in REGULATORY_XML_SPECS:
        (month / spec.filename).write_text(_xml(spec), encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    source_config = ConfiguredSourceConfig(
        xml_confia=XMLConfiaSourceConfig(enabled=True, root=str(tmp_path))
    )
    factory = DemoApplicationFactory(
        DemoConfig(
            execution_mode="CONFIGURED",
            demo_mode_enabled=False,
            data_cutoff_date=date(2026, 9, 30),
        ),
        source_config=source_config,
    )
    window = FinancialIntelligenceMainWindow(demo_factory=factory)
    window.open_workspace("rate_risk")
    workspace = window.workspace.currentWidget()

    assert isinstance(workspace, RateRiskWorkspace)
    assert workspace.is_configured is False
    assert workspace._regulatory_xml_panel is not None
    assert workspace.view._tabs.tabText(6) == "XML Brechas / Calce"
    panel = workspace._regulatory_xml_panel
    assert panel._headline.text() == "XML regulatorios conciliados"
    assert panel._files.rowCount() == 2
    assert panel._rows.rowCount() == 2
    assert panel._account_selector.count() == 3
    panel._account_selector.setCurrentIndex(1)
    assert panel._rows.rowCount() == 1
    assert panel._rows.item(0, 0).text() == "BRECHAS"
    panel._account_selector.setCurrentIndex(2)
    assert panel._rows.rowCount() == 1
    assert panel._rows.item(0, 0).text() == "CALCE"
    assert workspace.view._analysis_status_label.text() == "Estado: Sin cálculo"
    assert all(value.text() == "N/D" for value in workspace.view._kpi_values.values())

    window.close()
    app.processEvents()


def test_rtib_xml_tab_shows_unconfigured_state_without_data() -> None:
    app = QApplication.instance() or QApplication([])
    factory = DemoApplicationFactory(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False),
        source_config=ConfiguredSourceConfig(),
    )
    window = FinancialIntelligenceMainWindow(demo_factory=factory)
    window.open_workspace("rate_risk")
    workspace = window.workspace.currentWidget()
    assert isinstance(workspace, RateRiskWorkspace)
    panel = workspace._regulatory_xml_panel
    assert workspace.view._tabs.tabText(6) == "XML Brechas / Calce"
    assert "no configurada" in panel._headline.text()
    assert panel._rows.rowCount() == 0
    assert workspace.view._analysis_status_label.text() == "Estado: Sin cálculo"
    window.close()
    app.processEvents()
