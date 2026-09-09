"""Tests for money module.

Comprehensive tests for Currency, Money, ExchangeRate, and MoneyArithmetic.
"""

from datetime import date
from decimal import Decimal

import pytest

from aip.shared.money import Currency, ExchangeRate, Money, MoneyArithmetic


class TestCurrency:
    """Tests for Currency enumeration."""

    def test_currency_enum_values(self) -> None:
        assert Currency.USD.value == "USD"
        assert Currency.EUR.value == "EUR"
        assert Currency.GBP.value == "GBP"
        assert Currency.CRC.value == "CRC"

    def test_currency_string_representation(self) -> None:
        assert str(Currency.USD) == "USD"
        assert str(Currency.EUR) == "EUR"

    def test_currency_from_code_valid(self) -> None:
        result = Currency.from_code("USD")
        assert result == Currency.USD

    def test_currency_from_code_invalid_raises_error(self) -> None:
        from aip.shared.validation.exceptions import InvalidFormatError

        with pytest.raises(InvalidFormatError):
            Currency.from_code("INVALID")

    def test_currency_from_code_lowercase_raises_error(self) -> None:
        with pytest.raises(Exception):
            Currency.from_code("usd")

    def test_currency_from_code_unknown_valid_format_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            Currency.from_code("XXX")


class TestMoney:
    """Tests for Money value object."""

    def test_money_creation(self) -> None:
        money = Money(Decimal("100.50"), Currency.USD)
        assert money.amount == Decimal("100.50")
        assert money.currency == Currency.USD

    def test_money_string_representation(self) -> None:
        money = Money(Decimal("100.50"), Currency.USD)
        assert str(money) == "USD 100.50"

    def test_money_repr(self) -> None:
        money = Money(Decimal("100.50"), Currency.USD)
        assert "Money" in repr(money)
        assert "100.50" in repr(money)

    def test_money_equality(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("100"), Currency.USD)
        money3 = Money(Decimal("150"), Currency.USD)
        assert money1 == money2
        assert money1 != money3

    def test_money_equality_different_currency(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("100"), Currency.EUR)
        assert money1 != money2

    def test_money_hash(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("100"), Currency.USD)
        assert hash(money1) == hash(money2)

    def test_money_less_than(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("150"), Currency.USD)
        assert money1 < money2

    def test_money_greater_than(self) -> None:
        money1 = Money(Decimal("150"), Currency.USD)
        money2 = Money(Decimal("100"), Currency.USD)
        assert money1 > money2

    def test_money_less_equal_and_greater_equal(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("100"), Currency.USD)
        money3 = Money(Decimal("101"), Currency.USD)
        assert money1 <= money2
        assert money1 <= money3
        assert money3 >= money2

    def test_money_equality_with_other_type(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        assert (money == 100) is False

    def test_money_addition(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("50"), Currency.USD)
        result = money1 + money2
        assert result.amount == Decimal("150.00")
        assert result.currency == Currency.USD

    def test_money_addition_different_currencies_raises_error(self) -> None:
        money1 = Money(Decimal("100"), Currency.USD)
        money2 = Money(Decimal("50"), Currency.EUR)
        with pytest.raises(ValueError):
            money1 + money2

    def test_money_subtraction(self) -> None:
        money1 = Money(Decimal("150"), Currency.USD)
        money2 = Money(Decimal("50"), Currency.USD)
        result = money1 - money2
        assert result.amount == Decimal("100.00")
        assert result.currency == Currency.USD

    def test_money_multiplication(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        result = money * Decimal("1.5")
        assert result.amount == Decimal("150.00")
        assert result.currency == Currency.USD

    def test_money_multiplication_by_float(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        result = money * 1.5
        assert result.amount == Decimal("150.00")

    def test_money_multiplication_reverse(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        result = 1.5 * money
        assert result.amount == Decimal("150.00")

    def test_money_division(self) -> None:
        money = Money(Decimal("200"), Currency.USD)
        result = money / 2
        assert result.amount == Decimal("100.00")
        assert result.currency == Currency.USD

    def test_money_division_by_zero_raises_error(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        with pytest.raises(ValueError):
            money / 0

    def test_money_negation(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        result = -money
        assert result.amount == Decimal("-100")
        assert result.currency == Currency.USD

    def test_money_absolute_value(self) -> None:
        money = Money(Decimal("-100"), Currency.USD)
        result = money.abs()
        assert result.amount == Decimal("100")

    def test_money_is_positive(self) -> None:
        positive = Money(Decimal("100"), Currency.USD)
        zero = Money(Decimal("0"), Currency.USD)
        negative = Money(Decimal("-100"), Currency.USD)
        assert positive.is_positive() is True
        assert zero.is_positive() is False
        assert negative.is_positive() is False

    def test_money_is_negative(self) -> None:
        positive = Money(Decimal("100"), Currency.USD)
        zero = Money(Decimal("0"), Currency.USD)
        negative = Money(Decimal("-100"), Currency.USD)
        assert positive.is_negative() is False
        assert zero.is_negative() is False
        assert negative.is_negative() is True

    def test_money_is_zero(self) -> None:
        positive = Money(Decimal("100"), Currency.USD)
        zero = Money(Decimal("0"), Currency.USD)
        assert positive.is_zero() is False
        assert zero.is_zero() is True


class TestExchangeRate:
    """Tests for ExchangeRate value object."""

    def test_exchange_rate_creation(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("0.92"), date(2024, 7, 27))
        assert rate.from_currency == Currency.USD
        assert rate.to_currency == Currency.EUR
        assert rate.rate == Decimal("0.92")

    def test_exchange_rate_string_representation(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("0.92"), date(2024, 7, 27))
        assert "0.92" in str(rate)

    def test_exchange_rate_same_currency_raises_error(self) -> None:
        with pytest.raises(ValueError):
            ExchangeRate(Currency.USD, Currency.USD, Decimal("1"), date(2024, 7, 27))

    def test_exchange_rate_convert(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("0.92"), date(2024, 7, 27))
        usd_money = Money(Decimal("100"), Currency.USD)
        eur_money = rate.convert(usd_money)
        assert eur_money.currency == Currency.EUR
        assert eur_money.amount == Decimal("92.00")

    def test_exchange_rate_convert_wrong_currency_raises_error(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("0.92"), date(2024, 7, 27))
        gbp_money = Money(Decimal("100"), Currency.GBP)
        with pytest.raises(ValueError):
            rate.convert(gbp_money)

    def test_exchange_rate_inverse(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("0.92"), date(2024, 7, 27))
        inverse = rate.inverse()
        assert inverse.from_currency == Currency.EUR
        assert inverse.to_currency == Currency.USD
        assert inverse.rate > 1

    def test_exchange_rate_inverse_zero_rate_raises_error(self) -> None:
        rate = ExchangeRate(Currency.USD, Currency.EUR, Decimal("1.0"), date(2024, 7, 27))
        object.__setattr__(rate, "rate", Decimal("0"))
        with pytest.raises(ValueError):
            rate.inverse()


class TestMoneyArithmetic:
    """Tests for MoneyArithmetic utility."""

    def test_sum_money_same_currency(self) -> None:
        amounts = [
            Money(Decimal("100"), Currency.USD),
            Money(Decimal("50"), Currency.USD),
            Money(Decimal("25"), Currency.USD),
        ]
        result = MoneyArithmetic.sum_money(amounts)
        assert result.amount == Decimal("175.00")
        assert result.currency == Currency.USD

    def test_sum_money_single_amount(self) -> None:
        amounts = [Money(Decimal("100"), Currency.USD)]
        result = MoneyArithmetic.sum_money(amounts)
        assert result.amount == Decimal("100.00")

    def test_sum_money_empty_raises_error(self) -> None:
        with pytest.raises(Exception):
            MoneyArithmetic.sum_money([])

    def test_sum_money_different_currencies_raises_error(self) -> None:
        amounts = [
            Money(Decimal("100"), Currency.USD),
            Money(Decimal("50"), Currency.EUR),
        ]
        with pytest.raises(ValueError):
            MoneyArithmetic.sum_money(amounts)

    def test_average_money(self) -> None:
        amounts = [
            Money(Decimal("100"), Currency.USD),
            Money(Decimal("200"), Currency.USD),
        ]
        result = MoneyArithmetic.average_money(amounts)
        assert result.amount == Decimal("150.00")

    def test_multiply_money_utility(self) -> None:
        money = Money(Decimal("100"), Currency.USD)
        result = MoneyArithmetic.multiply_money(money, Decimal("1.5"))
        assert result.amount == Decimal("150.00")
