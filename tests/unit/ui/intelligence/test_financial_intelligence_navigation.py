from __future__ import annotations

from aip.ui.shell.intelligence_main_window import FinancialIntelligenceMainWindow
from aip.ui.shell.ribbon import Ribbon
from aip.ui.shell.sidebar import Sidebar


def test_financial_intelligence_route_is_exposed_by_shell_components() -> None:
    assert "Agente IA" in Ribbon._LABELS
    assert ("Agente IA", "financial_intelligence") in Sidebar._ITEMS
    assert FinancialIntelligenceMainWindow._WORKSPACE_TITLES["financial_intelligence"] == "Agente IA"
