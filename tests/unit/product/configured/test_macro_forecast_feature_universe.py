from __future__ import annotations

from aip.product.configured.readers.sugef_macro_feature_reader import (
    SUGEFMacroFeatureReader,
)
from aip.product.economic.econometric_dataset_builder import EconometricDatasetBuilder


def test_sugef_macro_feature_aliases_cover_governed_financial_drivers() -> None:
    cases = {
        "Margen de Interm Financiera": "SUGEF_MARGIN_INTERMEDIATION",
        "Rentabilidad nominal sobre patrimonio promedio": "SUGEF_ROE",
        "Cartera de crédito al día": "SUGEF_CURRENT_PORTFOLIO",
        "Cobertura de cartera en atraso": "SUGEF_COVERAGE_ARREARS",
        "Morosidad >90d y cobro judicial / Cartera Directa": "SUGEF_DELINQUENCY_90",
        "Gastos de Administración / Utilidad Operacional Bruta": "SUGEF_OPERATING_EFFICIENCY",
        "Gasto administrativo sobre activos": "SUGEF_ADMIN_EXPENSE_ASSETS",
        "Compromiso Patrimonial": "SUGEF_EQUITY_COMMITMENT",
        "Suficiencia Patrimonial": "SUGEF_CAPITAL_ADEQUACY",
        "Disponibilidades e Inversiones disponibles / Obligaciones público": (
            "SUGEF_LIQUIDITY_COVERAGE"
        ),
    }

    for label, expected in cases.items():
        assert SUGEFMacroFeatureReader._feature_code(label) == expected


def test_econometric_panel_includes_full_bccr_tri_curve_and_both_fx_rates() -> None:
    indicators = set(EconometricDatasetBuilder.MONTHLY_INDICATORS)

    assert {"FX_BUY", "FX_SELL", "TPM", "TBP", "INFLATION", "IMAE"}.issubset(indicators)
    for currency in ("CRC", "USD"):
        for tenor in ("1W", "1M", "3M", "6M", "9M", "12M", "24M", "36M", "60M"):
            assert f"TRI_{currency}_{tenor}" in indicators
