from datetime import date
from decimal import Decimal

import openpyxl
from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
    FolderWatchSourceConfig,
)
from aip.product.demo.configuration.demo_config import DemoConfig

from aip.product.configured.adapters.configured_portfolio_provider import (
    ConfiguredPortfolioProvider,
)
from aip.product.configured.services.configured_portfolio_valuation_comparison_service import (
    ConfiguredPortfolioValuationComparisonService,
)


def test_xlsx_preserves_missing_values_currency_and_lineage_through_provider(tmp_path):
    master = tmp_path / "Inversiones" / "2026" / "maestro" / "setiembre"
    master.mkdir(parents=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["ISIN", "Emisor", "Moneda", "Valor de Mercado", "Valor en Libros"])
    sheet.append(["TEST1", "Issuer", "CRC", 110, 100])
    sheet.append(["TEST2", "Issuer", "USD", 90, 100])
    sheet.append(["TEST3", "Issuer", "CRC", None, 100])
    sheet.append(["TEST4", "Issuer", None, 110, 100])
    workbook.save(master / "30-09-2026.xlsx")
    provider = ConfiguredPortfolioProvider(
        DemoConfig(
            execution_mode="CONFIGURED", demo_mode_enabled=False, data_cutoff_date=date(2026, 9, 30)
        ),
        ConfiguredSourceConfig(
            folder_watch=FolderWatchSourceConfig(enabled=True, portfolio_root=str(tmp_path))
        ),
    )
    payload = provider.get_portfolio()
    result = ConfiguredPortfolioValuationComparisonService.calculate(payload)
    assert len(result.rows) == 4
    assert result.rows[0].difference == Decimal("10")
    assert result.rows[1].difference == Decimal("-10")
    assert result.rows[2].difference is None
    assert result.rows[3].difference is None
    assert result.rows[0].source.source_reference == "30-09-2026.xlsx · fila 2"
    crc = next(total for total in result.totals if total.currency == "CRC")
    assert (crc.included_count, crc.total_count) == (1, 2)


def test_legacy_zero_and_currency_defaults_are_never_comparison_evidence():
    result = ConfiguredPortfolioValuationComparisonService.calculate(
        {"positions": [{"currency": "CRC", "market_value": 0, "book_value": 100}]}
    )
    assert result.rows[0].difference is None
    for value in (None, True, "bad", "NaN", "Infinity"):
        assert ConfiguredPortfolioValuationComparisonService._amount(value) is None
