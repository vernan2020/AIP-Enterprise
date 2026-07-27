"""Transaction entity implementation."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from src.aip.domain.portfolio.enums.transaction_type import TransactionType
from src.aip.domain.portfolio.exceptions import InvalidTransactionError
from src.aip.domain.portfolio.value_objects.portfolio_id import PortfolioId
from src.aip.domain.portfolio.value_objects.position_id import PositionId
from src.aip.domain.portfolio.value_objects.quantity import Quantity
from src.aip.domain.portfolio.value_objects.settlement_date import SettlementDate
from src.aip.domain.portfolio.value_objects.transaction_id import TransactionId
from src.aip.shared.money import Currency, Money


@dataclass(frozen=True, slots=True)
class Transaction:
    """Immutable transaction entity for portfolio bookkeeping."""

    transaction_id: TransactionId
    portfolio_id: PortfolioId
    position_id: PositionId
    transaction_type: TransactionType
    trade_date: date
    settlement_date: SettlementDate
    quantity: Quantity
    nominal_amount: Money
    gross_amount: Money
    fees: Money
    taxes: Money
    net_amount: Money
    currency: Currency
    reference: str
    created_at: datetime

    def __post_init__(self) -> None:
        self._validate_currency_consistency()
        self._validate_reference()
        self._validate_net_amount_formula()
        self._validate_type_sign_consistency()

    @classmethod
    def buy(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        nominal_amount: Decimal,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create a BUY transaction from absolute amounts."""
        return cls._create_signed(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=TransactionType.BUY,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=-abs(nominal_amount),
            gross_amount=-abs(gross_amount),
            fees=abs(fees),
            taxes=abs(taxes),
            currency=currency,
            reference=reference,
        )

    @classmethod
    def sell(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        nominal_amount: Decimal,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create a SELL transaction from absolute amounts."""
        return cls._create_signed(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=TransactionType.SELL,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=abs(nominal_amount),
            gross_amount=abs(gross_amount),
            fees=abs(fees),
            taxes=abs(taxes),
            currency=currency,
            reference=reference,
        )

    @classmethod
    def coupon(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create a COUPON transaction from absolute cashflow components."""
        return cls._create_signed(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=TransactionType.COUPON,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=abs(gross_amount),
            gross_amount=abs(gross_amount),
            fees=abs(fees),
            taxes=abs(taxes),
            currency=currency,
            reference=reference,
        )

    @classmethod
    def maturity(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        nominal_amount: Decimal,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create a MATURITY transaction from absolute amounts."""
        return cls._create_signed(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=TransactionType.MATURITY,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=abs(nominal_amount),
            gross_amount=abs(gross_amount),
            fees=abs(fees),
            taxes=abs(taxes),
            currency=currency,
            reference=reference,
        )

    @classmethod
    def adjustment(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        nominal_amount: Decimal,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create an ADJUSTMENT transaction preserving explicit signs."""
        return cls._create_signed(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=TransactionType.ADJUSTMENT,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=nominal_amount,
            gross_amount=gross_amount,
            fees=abs(fees),
            taxes=abs(taxes),
            currency=currency,
            reference=reference,
        )

    @classmethod
    def _create_signed(
        cls,
        transaction_id: TransactionId,
        portfolio_id: PortfolioId,
        position_id: PositionId,
        transaction_type: TransactionType,
        trade_date: date,
        settlement_date: SettlementDate,
        quantity: Quantity,
        nominal_amount: Decimal,
        gross_amount: Decimal,
        fees: Decimal,
        taxes: Decimal,
        currency: Currency,
        reference: str,
    ) -> "Transaction":
        """Create a transaction enforcing reproducible net amount formula."""
        gross_money = Money(gross_amount, currency)
        fees_money = Money(fees, currency)
        taxes_money = Money(taxes, currency)
        net_money = gross_money - fees_money - taxes_money

        return cls(
            transaction_id=transaction_id,
            portfolio_id=portfolio_id,
            position_id=position_id,
            transaction_type=transaction_type,
            trade_date=trade_date,
            settlement_date=settlement_date,
            quantity=quantity,
            nominal_amount=Money(nominal_amount, currency),
            gross_amount=gross_money,
            fees=fees_money,
            taxes=taxes_money,
            net_amount=net_money,
            currency=currency,
            reference=reference.strip(),
            created_at=datetime.now(timezone.utc),
        )

    def _validate_currency_consistency(self) -> None:
        """Ensure all monetary fields share transaction currency."""
        fields = [self.nominal_amount, self.gross_amount, self.fees, self.taxes, self.net_amount]
        for field in fields:
            if field.currency != self.currency:
                raise InvalidTransactionError("All transaction monetary fields must share the same currency.")

    def _validate_reference(self) -> None:
        """Ensure transaction reference is present."""
        if not self.reference:
            raise InvalidTransactionError("Transaction reference cannot be empty.")

    def _validate_net_amount_formula(self) -> None:
        """Validate net amount is reproducible from gross, fees, and taxes."""
        expected = self.gross_amount - self.fees - self.taxes
        if expected.amount != self.net_amount.amount:
            raise InvalidTransactionError("Net amount is not reproducible from gross, fees, and taxes.")

    def _validate_type_sign_consistency(self) -> None:
        """Validate sign conventions according to transaction type."""
        if self.fees.amount < Decimal("0") or self.taxes.amount < Decimal("0"):
            raise InvalidTransactionError("Fees and taxes must be non-negative.")

        if self.transaction_type == TransactionType.BUY:
            if not (self.nominal_amount.amount < 0 and self.gross_amount.amount < 0 and self.net_amount.amount < 0):
                raise InvalidTransactionError("BUY transactions must have negative nominal, gross and net.")

        elif self.transaction_type in {
            TransactionType.SELL,
            TransactionType.COUPON,
            TransactionType.MATURITY,
        }:
            if not (self.nominal_amount.amount > 0 and self.gross_amount.amount > 0 and self.net_amount.amount > 0):
                raise InvalidTransactionError(
                    "SELL/COUPON/MATURITY transactions must have positive nominal, gross and net."
                )

        elif self.transaction_type == TransactionType.ADJUSTMENT:
            if self.nominal_amount.amount == Decimal("0") and self.gross_amount.amount == Decimal("0"):
                raise InvalidTransactionError("ADJUSTMENT transaction cannot be zero on both nominal and gross.")
