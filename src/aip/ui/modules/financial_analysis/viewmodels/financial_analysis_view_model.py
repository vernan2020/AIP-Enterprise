from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FinancialMetricView:
    code: str
    label: str
    value: str
    change: str
    source_account: str


@dataclass(frozen=True, slots=True)
class FinancialStatementRow:
    statement: str
    account_code: str
    account_name: str
    amount: str
    currency: str
    trace: str


@dataclass(frozen=True, slots=True)
class PeerSummaryRow:
    entity_id: str
    entity_name: str
    category: str
    assets: str
    loans: str
    equity: str
    net_income: str
    roa: str
    roe: str


@dataclass(frozen=True, slots=True)
class RatingDimensionRow:
    name: str
    score: str
    weight: str
    coverage: str


@dataclass(frozen=True, slots=True)
class RatingIndicatorRow:
    indicator: str
    dimension: str
    value: str
    percentile_15: str
    midpoint: str
    percentile_85: str
    direction: str
    level: str
    contribution: str
    source_account: str


@dataclass(frozen=True, slots=True)
class FinancialAnalysisViewModel:
    title: str = "ANÁLISIS FINANCIERO"
    subtitle: str = "Estados financieros y comparación de entidades supervisadas por SUGEF"
    status: str = "UNAVAILABLE"
    cutoff_date: str = "-"
    selected_entity_id: str = ""
    selected_entity_name: str = "Sin datos"
    entities: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    metrics: tuple[FinancialMetricView, ...] = field(default_factory=tuple)
    statement_rows: tuple[FinancialStatementRow, ...] = field(default_factory=tuple)
    peer_rows: tuple[PeerSummaryRow, ...] = field(default_factory=tuple)
    rating_status: str = "INCOMPLETE"
    rating_score: str = "-"
    rating_grade: str = "Sin emitir"
    rating_coverage: str = "0.00%"
    rating_methodology: str = "08ME14-01"
    rating_dimensions: tuple[RatingDimensionRow, ...] = field(default_factory=tuple)
    rating_indicators: tuple[RatingIndicatorRow, ...] = field(default_factory=tuple)
    rating_diagnostics: tuple[str, ...] = field(default_factory=tuple)
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    source_name: str = "SUGEF"
    source_url: str = "https://www.sugef.fi.cr/reportes/Informacion_Financiera_Contable.aspx"
    source_file_count: int = 0
