from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_financial_history_reader import (
    SUGEFFinancialHistoryReader,
)
from aip.product.economic.econometric_dataset import EconometricDataPoint


@dataclass(frozen=True, slots=True)
class SUGEFMacroFeatureReadResult:
    """Lag-safe monthly SUGEF banking indicators usable as exogenous ML features."""

    points: tuple[EconometricDataPoint, ...]
    diagnostics: tuple[str, ...]


class SUGEFMacroFeatureReader:
    """Read a governed subset of SUGEF entity indicators for macro ML models.

    The forecasting targets remain official BCCR macro/market series. SUGEF
    indicators are explanatory features only and are always aligned to their
    original monthly publication period; this reader never interpolates,
    forward-fills or back-fills missing observations.
    """

    LOOKBACK_MONTHS = 119
    FEATURE_CODES = (
        "SUGEF_MARGIN_INTERMEDIATION",
        "SUGEF_ROA",
        "SUGEF_ROE",
        "SUGEF_CURRENT_PORTFOLIO",
        "SUGEF_COVERAGE_ARREARS",
        "SUGEF_DELINQUENCY_90",
        "SUGEF_OPERATING_EFFICIENCY",
        "SUGEF_ADMIN_EXPENSE_ASSETS",
        "SUGEF_EQUITY_COMMITMENT",
        "SUGEF_CAPITAL_ADEQUACY",
        "SUGEF_LIQUIDITY_COVERAGE",
    )

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        self._config = config
        self._reader = SUGEFFinancialHistoryReader(config)

    def read(self, cutoff_date: date) -> SUGEFMacroFeatureReadResult:
        if not self._config.enabled:
            return SUGEFMacroFeatureReadResult((), ("SUGEF macro features disabled.",))
        if not self._config.api_entity_codes:
            return SUGEFMacroFeatureReadResult(
                (),
                ("SUGEF macro features: entity not configured.",),
            )

        entity_id = self._config.api_entity_codes[0]
        result = self._reader.read_entity_history_range(
            entity_id,
            cutoff_date,
            lookback_months=self.LOOKBACK_MONTHS,
        )
        selected: dict[tuple[str, date], EconometricDataPoint] = {}
        for line in result.lines:
            if line.entity.entity_id != entity_id:
                continue
            if line.statement_type is not FinancialStatementType.INDICATORS:
                continue
            feature_code = self._feature_code(line.account_name)
            if feature_code is None:
                continue
            point = EconometricDataPoint(
                indicator_code=feature_code,
                period=line.statement_date,
                value=line.amount,
                observation_date=line.statement_date,
                source="SUGEF",
                source_series_code=line.account_code or None,
            )
            selected[(feature_code, line.statement_date)] = point

        points = tuple(
            sorted(
                selected.values(),
                key=lambda item: (item.period, item.indicator_code),
            )
        )
        diagnostics = (
            *result.diagnostics,
            f"SUGEF ML features: {len(points)} observations for entity {entity_id}.",
        )
        return SUGEFMacroFeatureReadResult(points, diagnostics)

    @classmethod
    def _feature_code(cls, account_name: str) -> str | None:
        name = cls._normalize(account_name)
        rules = (
            ("SUGEF_MARGIN_INTERMEDIATION", ("MARGEN DE INTERM", "FINANCIERA")),
            ("SUGEF_ROA", ("ROA",)),
            ("SUGEF_ROE", ("ROE",)),
            ("SUGEF_ROE", ("RENTABILIDAD", "PATRIMONIO")),
            ("SUGEF_CURRENT_PORTFOLIO", ("CARTERA DE CREDITO AL DIA",)),
            ("SUGEF_COVERAGE_ARREARS", ("COBERTURA", "CARTERA", "ATRASO")),
            ("SUGEF_DELINQUENCY_90", ("MOROSIDAD", "90", "CARTERA")),
            ("SUGEF_OPERATING_EFFICIENCY", ("EFICIENCIA OPERATIVA",)),
            ("SUGEF_OPERATING_EFFICIENCY", ("GASTOS DE ADMINISTRACION", "UTILIDAD OPERACIONAL")),
            ("SUGEF_ADMIN_EXPENSE_ASSETS", ("GASTO", "ADMINISTR", "ACTIVOS")),
            ("SUGEF_EQUITY_COMMITMENT", ("COMPROMISO PATRIMONIAL",)),
            ("SUGEF_CAPITAL_ADEQUACY", ("SUFICIENCIA PATRIMONIAL",)),
            (
                "SUGEF_LIQUIDITY_COVERAGE",
                ("DISPONIBILIDADES", "INVERSIONES", "OBLIGACIONES"),
            ),
        )
        for code, tokens in rules:
            if all(token in name for token in tokens):
                return code
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(ascii_text.upper().replace("/", " ").split())
