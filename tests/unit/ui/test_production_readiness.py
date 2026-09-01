from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from aip.ui.dialogs.about_dialog import AboutDialog
from aip.ui.services.diagnostic_service import DiagnosticMetricsStore, ProductionReadinessService
from aip.ui.services.export_service import TableExportService
from aip.ui.shell.main_window import MainWindow
from aip.ui.widgets.health_center import HealthCenterWidget
from aip.ui.widgets.log_viewer import LogViewerDialog
from aip.ui.widgets.settings_center import SettingsCenterDialog


def test_diagnostic_mode_exposes_metrics() -> None:
    window = MainWindow()
    window.toggle_diagnostic_mode(True)
    metrics = window.diagnostic_snapshot()
    assert metrics["diagnostic_mode"] is True
    assert metrics["metrics"]["startup_time_ms"] >= 0
    assert "environment" in metrics


def test_health_center_widget_renders_components() -> None:
    widget = HealthCenterWidget()
    rows = widget.component_rows()
    assert any(row[0] == "Application" for row in rows)
    assert any(row[0] == "Scheduler" for row in rows)


def test_settings_center_dialog_is_read_only() -> None:
    dialog = SettingsCenterDialog()
    assert dialog.windowTitle() == "Settings Center"
    assert dialog.is_read_only() is True


def test_log_viewer_filters_and_exports() -> None:
    viewer = LogViewerDialog()
    viewer.add_log("INFO", "ui", "exec-1", "corr-1", "startup")
    viewer.add_log("ERROR", "scheduler", "exec-2", "corr-2", "refresh failed")
    viewer.apply_filters(level="ERROR")
    assert viewer.visible_log_count() == 1
    output = viewer.export_logs("json")
    assert output.endswith(".json")
    assert Path(output).exists()


def test_about_dialog_contains_release_information() -> None:
    dialog = AboutDialog()
    text = dialog.release_text()
    assert "AIP Enterprise" in text
    assert "Version" in text
    assert "Python" in text


def test_table_export_service_writes_supported_formats(tmp_path: Path) -> None:
    export_service = TableExportService()
    output = export_service.export_records(
        tmp_path / "table",
        headers=["name", "state"],
        rows=[["Application", "Healthy"]],
        export_format="csv",
    )
    assert output.endswith(".csv")
    assert Path(output).exists()


def test_diagnostic_metrics_store_tracks_refresh_duration() -> None:
    metrics = DiagnosticMetricsStore()
    metrics.record_refresh_all_duration(12.5)
    assert metrics.last_refresh_duration_ms == 12.5


def test_main_window_exports_current_workspace_table(tmp_path: Path) -> None:
    window = MainWindow()
    table = QTableWidget(2, 2)
    table.setHorizontalHeaderLabels(["name", "state"])
    table.setItem(0, 0, QTableWidgetItem("Application"))
    table.setItem(0, 1, QTableWidgetItem("Healthy"))

    window.workspace.add_tab("Export Test", table)
    output = window.export_current_workspace_table(
        tmp_path / "workspace-export", export_format="csv"
    )
    assert output.endswith(".csv")
    assert Path(output).exists()


def test_production_readiness_service_runs_stability_iterations() -> None:
    service = ProductionReadinessService(iterations=3)
    report = service.run_stability_check()
    assert report["iterations"] == 3
    assert report["failures"] == 0
    assert report["warnings"] == 0
