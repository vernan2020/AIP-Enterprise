from __future__ import annotations

from aip.ui.services.theme_service import ThemeService
from aip.ui.shell.ribbon import Ribbon
from aip.ui.themes.institutional_white import InstitutionalWhiteDesign
from aip.ui.themes.palette import ThemePalette


def test_default_theme_is_institutional_white() -> None:
    service = ThemeService()
    css = service.stylesheet()
    assert "QWidget#portfolioWorkspace" in css
    assert "QWidget#financialAnalysisWorkspace" in css
    assert "QWidget#liquidityWorkspace" in css
    assert "QToolBar#aipRibbon QToolButton:checked" in css
    assert ThemePalette.brand_blue in css
    assert 'font-family: "Lucida Sans Unicode"' in css


def test_white_design_covers_all_live_analytical_workspaces() -> None:
    css = InstitutionalWhiteDesign.stylesheet()
    for name in (
        "homeWorkspace",
        "executiveWorkspace",
        "portfolioWorkspace",
        "marketWorkspace",
        "priceRiskWorkspace",
        "rateRiskWorkspace",
        "macroIntelligenceWorkspace",
        "liquidityWorkspace",
        "treasuryWorkspace",
        "financialAnalysisWorkspace",
    ):
        assert f"QWidget#{name}" in css


def test_ribbon_marks_only_active_registered_module(qt_app) -> None:
    ribbon = Ribbon()
    try:
        ribbon.set_active_module("Portafolio")
        assert ribbon.action("Portafolio").isChecked()
        assert not ribbon.action("Mercado").isChecked()
        ribbon.set_active_module("Mercado")
        assert ribbon.action("Mercado").isChecked()
        assert not ribbon.action("Portafolio").isChecked()
    finally:
        ribbon.close()
        ribbon.deleteLater()
        qt_app.processEvents()
