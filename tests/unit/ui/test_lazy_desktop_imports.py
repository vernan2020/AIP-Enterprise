from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _probe(script: str) -> dict[str, bool]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_PROJECT_ROOT / "src")
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip())


def test_main_window_does_not_import_heavy_workspaces_eagerly() -> None:
    modules = (
        "aip.ui.modules.executive.views.executive_workspace",
        "aip.ui.modules.portfolio.views.portfolio_view",
        "aip.ui.modules.market.views.market_view",
        "aip.ui.modules.price_risk.views.price_risk_view",
        "aip.ui.modules.rate_risk.views.rate_risk_view",
        "aip.ui.modules.liquidity.views.liquidity_view",
        "aip.ui.modules.treasury.views.treasury_view",
    )
    script = (
        "import json, sys; import aip.ui.shell.main_window; "
        f"mods={modules!r}; "
        "print(json.dumps({name: name in sys.modules for name in mods}))"
    )
    loaded = _probe(script)
    assert not any(loaded.values()), loaded


def test_financial_intelligence_workspace_is_lazy() -> None:
    modules = (
        "aip.ui.modules.intelligence.presenters.financial_intelligence_presenter",
        "aip.ui.modules.intelligence.views.financial_intelligence_view",
    )
    script = (
        "import json, sys; import aip.ui.shell.intelligence_main_window; "
        f"mods={modules!r}; "
        "print(json.dumps({name: name in sys.modules for name in mods}))"
    )
    loaded = _probe(script)
    assert not any(loaded.values()), loaded


def test_advanced_forecasting_stack_is_lazy_until_forecast_execution() -> None:
    modules = ("pandas", "statsmodels")
    script = (
        "import json, sys; "
        "from aip.product.configured.services.configured_advanced_macro_forecasting_service "
        "import ConfiguredAdvancedMacroForecastingService; "
        "ConfiguredAdvancedMacroForecastingService(repository=object()); "
        f"mods={modules!r}; "
        "print(json.dumps({name: name in sys.modules for name in mods}))"
    )
    loaded = _probe(script)
    assert not any(loaded.values()), loaded
