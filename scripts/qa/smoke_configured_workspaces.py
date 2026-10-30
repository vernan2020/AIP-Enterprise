"""CI-only full-workspace GUI smoke in offline CONFIGURED mode.

Uses no demo data and no institutional sources; checks that the application shell
can instantiate its workspaces without network access or fabricated balances.
"""

from __future__ import annotations

import os

os.environ["AIP_EXECUTION_MODE"] = "CONFIGURED"
os.environ["AIP_DEMO_MODE_ENABLED"] = "false"
os.environ["AIP_BCCR_ENABLED"] = "false"
os.environ["AIP_SUGEF_FINANCIAL_API_ENABLED"] = "false"
os.environ["AIP_SQLSERVER_ENABLED"] = "false"
os.environ["AIP_FOLDERWATCH_ENABLED"] = "false"
os.environ["AIP_VECTOR_ENABLED"] = "false"
os.environ["AIP_CURVES_ENABLED"] = "false"
os.environ["AIP_XML_CONFIA_ENABLED"] = "false"
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from aip.ui.shell.intelligence_main_window import (  # noqa: E402
    FinancialIntelligenceMainWindow,
)

ROUTES = (
    "home",
    "executive",
    "portfolio",
    "market",
    "price_risk",
    "macro_intelligence",
    "liquidity",
    "treasury",
    "financial_analysis",
    "rate_risk",
    "financial_intelligence",
)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = FinancialIntelligenceMainWindow()
    try:
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        failures: list[str] = []
        for route in ROUTES:
            try:
                window.open_workspace(route)
                app.processEvents()
                widget = window.workspace.currentWidget()
                if widget is None:
                    raise RuntimeError("workspace missing")
                if route == "liquidity":
                    tabs = widget.findChildren(QTabWidget)
                    names = {
                        tab.tabText(index)
                        for tab in tabs
                        for index in range(tab.count())
                    }
                    for required in (
                        "Flujo proyectado · SUGEF 2-10",
                        "Conciliación inversiones",
                        "Estado de fuentes",
                        "Trazabilidad por operación",
                        "Conciliación captaciones vista",
                    ):
                        if required not in names:
                            raise RuntimeError("SUGEF210 operational tab unavailable")
                if route == "rate_risk":
                    tabs = widget.findChildren(QTabWidget)
                    tab_text = {
                        tab.tabText(index)
                        for tab in tabs
                        for index in range(tab.count())
                    }
                    for needed in (
                        "GAP SUGEF · 19 bandas",
                        "Bandeo 19 · evidencia",
                        "XML contractual · auditoría",
                        "Inversiones · Maestro",
                    ):
                        if needed not in tab_text:
                            raise RuntimeError("required RTILB tab missing")
                print(f"PASS {route}", flush=True)
            except Exception:
                failures.append(route)
                print(f"FAIL {route}: workspace did not load", flush=True)
        if failures:
            print(f"BLOCKED: {len(failures)} workspace(s) failed", flush=True)
            return 1
        print(f"PASS CONFIGURED_GLOBAL_UI_SMOKE {len(ROUTES)} workspaces", flush=True)
        return 0
    finally:
        for index in reversed(range(window.workspace.count())):
            widget = window.workspace.widget(index)
            if widget is not None:
                widget.close()
        QThreadPool.globalInstance().waitForDone(15000)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
