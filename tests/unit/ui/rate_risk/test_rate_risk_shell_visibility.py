from aip.ui.shell.intelligence_main_window import FinancialIntelligenceMainWindow
from aip.ui.shell.ribbon import Ribbon
from aip.ui.shell.sidebar import Sidebar

RATE_RISK_LABEL = "Riesgo de Tasas · RTILB"
RATE_RISK_ROUTE = "rate_risk"


def test_rate_risk_is_exposed_by_certified_shell_navigation() -> None:
    assert RATE_RISK_LABEL in Ribbon._LABELS
    assert (RATE_RISK_LABEL, RATE_RISK_ROUTE) in Sidebar._ITEMS
    assert FinancialIntelligenceMainWindow._WORKSPACE_TITLES[RATE_RISK_ROUTE] == RATE_RISK_LABEL
