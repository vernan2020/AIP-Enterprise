from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.intelligence.engine import FinancialIntelligenceEngine
from aip.domain.intelligence.models import (
    FinancialIntelligenceContext,
    IntelligenceSeverity,
    MarketOpportunity,
)


def _context(**overrides: object) -> FinancialIntelligenceContext:
    values: dict[str, object] = {
        "cutoff_date": date(2026, 8, 31),
        "execution_mode": "CONFIGURED",
        "data_quality_status": "HEALTHY",
        "source_states": ("portfolio=HEALTHY",),
        "warnings": (),
        "market_value_crc": Decimal("306330000000"),
        "weighted_yield_percent": Decimal("5.20"),
        "modified_duration": Decimal("1.46"),
        "hqla_percent": Decimal("67.3"),
        "dv01_crc": Decimal("35450000"),
        "issuer_hhi": Decimal("3799"),
        "government_bccr_share_percent": Decimal("84"),
        "duration_under_1_share_percent": Decimal("35"),
        "duration_1_5_share_percent": Decimal("40"),
        "duration_over_5_share_percent": Decimal("25"),
        "icl_total": Decimal("9.49"),
        "hqla_capacity_crc": Decimal("200000000000"),
        "hqla_restricted_count": 0,
        "liquidity_policy_status": "Cumple",
        "liquidity_stress_result": "Stable",
        "opportunities": (),
    }
    values.update(overrides)
    return FinancialIntelligenceContext(**values)  # type: ignore[arg-type]


def test_engine_detects_policy_limit_breaches_without_llm() -> None:
    report = FinancialIntelligenceEngine().analyze(
        _context(
            modified_duration=Decimal("3.20"),
            government_bccr_share_percent=Decimal("91"),
            duration_over_5_share_percent=Decimal("34"),
        )
    )

    finding_ids = {item.finding_id for item in report.findings}
    assert "portfolio-duration-limit" in finding_ids
    assert "portfolio-sovereign-concentration" in finding_ids
    assert "portfolio-bucket-over-5" in finding_ids
    assert any(item.severity is IntelligenceSeverity.CRITICAL for item in report.findings)


def test_engine_preserves_data_quality_guardrail() -> None:
    report = FinancialIntelligenceEngine().analyze(_context(data_quality_status="DEGRADED"))

    finding = next(item for item in report.findings if item.finding_id == "data-quality")
    assert finding.severity is IntelligenceSeverity.HIGH
    assert "No ejecutar una estrategia" in finding.recommendation


def test_engine_surfaces_relative_value_as_opportunity_not_order() -> None:
    report = FinancialIntelligenceEngine().analyze(
        _context(
            opportunities=(
                MarketOpportunity(
                    series="BCCR 2029",
                    issuer="BCCR",
                    spread_bp=Decimal("42.5"),
                    classification="HQLA",
                ),
            )
        )
    )

    finding = next(item for item in report.findings if item.finding_id == "market-relative-value")
    assert finding.severity is IntelligenceSeverity.OPPORTUNITY
    assert "no constituye una orden" in finding.recommendation.casefold()


def test_local_answer_is_grounded_in_selected_domain() -> None:
    engine = FinancialIntelligenceEngine()
    report = engine.analyze(
        _context(hqla_restricted_count=2, modified_duration=Decimal("3.10"))
    )

    answer = engine.answer(report, "¿Qué debo vigilar en liquidez y HQLA?")

    assert "Existen posiciones restringidas para HQLA" in answer
    assert "Duración modificada" not in answer
