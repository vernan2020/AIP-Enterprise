from __future__ import annotations

from datetime import date

from aip.product.configured.irrbb.borrowing_source_rules import BorrowingSourceRules


def test_month_end_cutoff_derives_august_2026_close() -> None:
    assert BorrowingSourceRules.month_end_cutoff("AGO-26") == date(2026, 8, 31)


def test_month_end_cutoff_handles_february_and_rejects_non_governed_labels() -> None:
    assert BorrowingSourceRules.month_end_cutoff("FEB-24") == date(2024, 2, 29)
    assert BorrowingSourceRules.month_end_cutoff("AGOSTO 2026") is None
    assert BorrowingSourceRules.month_end_cutoff("AGO_26") is None


def test_reset_frequency_uses_only_confirmed_actualizacion_values() -> None:
    assert BorrowingSourceRules.reset_frequency_months("MENSUAL") == 1
    assert BorrowingSourceRules.reset_frequency_months(" trimestral ") == 3
    assert BorrowingSourceRules.reset_frequency_months("SEMESTRAL") is None
    assert BorrowingSourceRules.reset_frequency_months(None) is None


def test_payment_day_is_strict() -> None:
    assert BorrowingSourceRules.payment_day(3) == 3
    assert BorrowingSourceRules.payment_day(24.0) == 24
    assert BorrowingSourceRules.payment_day("31") == 31
    assert BorrowingSourceRules.payment_day(0) is None
    assert BorrowingSourceRules.payment_day(32) is None
    assert BorrowingSourceRules.payment_day(3.5) is None


def test_next_monthly_repricing_uses_fecha_pago_after_cutoff() -> None:
    assert BorrowingSourceRules.next_monthly_repricing_date(
        cutoff_date=date(2026, 8, 31),
        payment_day=3,
        update_frequency="MENSUAL",
    ) == date(2026, 9, 3)


def test_quarterly_repricing_uses_opening_date_phase_and_month_after_quarter() -> None:
    assert BorrowingSourceRules.next_repricing_date(
        cutoff_date=date(2026, 8, 31),
        payment_day=23,
        update_frequency="TRIMESTRAL",
        opening_date=date(2025, 1, 15),
    ) == date(2026, 11, 23)


def test_quarterly_first_repricing_is_month_after_first_completed_quarter() -> None:
    assert BorrowingSourceRules.next_repricing_date(
        cutoff_date=date(2026, 4, 30),
        payment_day=10,
        update_frequency="TRIMESTRAL",
        opening_date=date(2026, 1, 10),
    ) == date(2026, 5, 10)


def test_quarterly_repricing_rolls_to_next_cycle_when_cutoff_is_on_reset_day() -> None:
    assert BorrowingSourceRules.next_repricing_date(
        cutoff_date=date(2026, 8, 23),
        payment_day=23,
        update_frequency="TRIMESTRAL",
        opening_date=date(2025, 1, 15),
    ) == date(2026, 11, 23)


def test_quarterly_repricing_fails_closed_without_opening_date_phase_anchor() -> None:
    assert (
        BorrowingSourceRules.next_repricing_date(
            cutoff_date=date(2026, 8, 31),
            payment_day=23,
            update_frequency="TRIMESTRAL",
        )
        is None
    )


def test_repricing_does_not_invent_invalid_calendar_day() -> None:
    assert (
        BorrowingSourceRules.next_repricing_date(
            cutoff_date=date(2026, 1, 31),
            payment_day=31,
            update_frequency="MENSUAL",
        )
        is None
    )
    assert (
        BorrowingSourceRules.next_repricing_date(
            cutoff_date=date(2026, 7, 31),
            payment_day=31,
            update_frequency="TRIMESTRAL",
            opening_date=date(2026, 3, 1),
        )
        is None
    )
