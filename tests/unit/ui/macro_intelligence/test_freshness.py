"""Macro freshness warnings are presentation-only, never reprice historic data."""

from datetime import date
from decimal import Decimal

from aip.product.economic.economic_viewmodel import (
    EconomicIndicatorCard,
    EconomicSnapshot,
)
from aip.ui.modules.macro_intelligence.freshness import economic_source_freshness_notice


def _card(code: str, observed: date) -> EconomicIndicatorCard:
    return EconomicIndicatorCard(
        code=code,
        name=code,
        value=Decimal("3.0"),
        previous_value=None,
        absolute_change=None,
        relative_change_percent=None,
        trend="STABLE",
        observation_date=observed,
        unit="%",
        source="BCCR",
        source_series_code=None,
        derived=False,
    )


def _snapshot(*, source: str, observed: date) -> EconomicSnapshot:
    return EconomicSnapshot(
        status="AVAILABLE",
        source=source,
        cutoff_date=observed,
        market_snapshot=(
            _card("FX_SELL", observed),
            _card("TPM", observed),
            _card("TBP", observed),
        ),
        tri_crc_curve=(),
        tri_usd_curve=(),
        diagnostics=(),
        cache_entries=0,
    )


def test_august_bccr_is_explicitly_flagged_in_october() -> None:
    value = economic_source_freshness_notice(
        _snapshot(source="BCCR · HISTÓRICO LOCAL", observed=date(2026, 8, 27)),
        as_of=date(2026, 10, 13),
    )
    assert "HISTÓRICO" in value.lower().upper()
    assert "FX_SELL: 27/08/2026" in value
    assert "TPM: 27/08/2026" in value
    assert "TBP: 27/08/2026" in value


def test_live_recent_market_observations_do_not_raise_warning() -> None:
    assert not economic_source_freshness_notice(
        _snapshot(source="BCCR", observed=date(2026, 10, 12)),
        as_of=date(2026, 10, 13),
    )


def test_local_history_always_discloses_non_live_origin() -> None:
    notice = economic_source_freshness_notice(
        _snapshot(source="BCCR · HISTÓRICO LOCAL", observed=date(2026, 10, 12)),
        as_of=date(2026, 10, 13),
    )
    assert "Sin actualización BCCR en línea" in notice
