from datetime import date

import pytest

from aip.product.configured.context.valuation_date_context import ValuationDateContext


def test_context_exposes_initial_date_and_updates_in_place() -> None:
    context = ValuationDateContext(date(2026, 8, 27))

    assert context.value == date(2026, 8, 27)
    assert context.set(date(2026, 8, 26)) is True
    assert context.value == date(2026, 8, 26)
    assert context.set(date(2026, 8, 26)) is False


def test_context_rejects_non_date_values() -> None:
    with pytest.raises(TypeError):
        ValuationDateContext("2026-08-27")  # type: ignore[arg-type]

    context = ValuationDateContext(date(2026, 8, 27))
    with pytest.raises(TypeError):
        context.set("2026-08-26")  # type: ignore[arg-type]
