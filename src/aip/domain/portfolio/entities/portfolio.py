"""Portfolio aggregate root implementation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.aip.domain.portfolio.entities.position import Position
from src.aip.domain.portfolio.entities.transaction import Transaction
from src.aip.domain.portfolio.enums.portfolio_status import PortfolioStatus
from src.aip.domain.portfolio.events import (
    DomainEvent,
    PortfolioCreated,
    PositionAdded,
    PositionRemoved,
    TransactionRegistered,
)
from src.aip.domain.portfolio.exceptions import (
    DuplicatePositionError,
    PortfolioClosedError,
    PositionNotFoundError,
)
from src.aip.domain.portfolio.services.portfolio_calculation_service import (
    PortfolioCalculationService,
)
from src.aip.domain.portfolio.value_objects.portfolio_id import PortfolioId
from src.aip.shared.money import Currency, Money


@dataclass(slots=True)
class Portfolio:
    """Aggregate root representing an investment portfolio."""

    portfolio_id: PortfolioId
    name: str
    description: str
    base_currency: Currency
    status: PortfolioStatus
    created_at: datetime
    positions: list[Position] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        portfolio_id: PortfolioId,
        name: str,
        description: str,
        base_currency: Currency,
    ) -> "Portfolio":
        """Create a new portfolio aggregate in CREATED state."""
        now = datetime.now(timezone.utc)
        portfolio = cls(
            portfolio_id=portfolio_id,
            name=name.strip(),
            description=description.strip(),
            base_currency=base_currency,
            status=PortfolioStatus.CREATED,
            created_at=now,
        )
        portfolio._record_event(
            PortfolioCreated.from_payload(
                aggregate_id=str(portfolio.portfolio_id),
                payload={
                    "name": portfolio.name,
                    "description": portfolio.description,
                    "base_currency": portfolio.base_currency.value,
                },
            )
        )
        return portfolio

    def activate(self) -> None:
        """Move portfolio status to ACTIVE."""
        if self.status == PortfolioStatus.CLOSED:
            raise PortfolioClosedError("Closed portfolio cannot be activated.")
        self.status = PortfolioStatus.ACTIVE
        self._record_state_event("portfolio.activated")

    def suspend(self) -> None:
        """Move portfolio status to SUSPENDED."""
        if self.status == PortfolioStatus.CLOSED:
            raise PortfolioClosedError("Closed portfolio cannot be suspended.")
        self.status = PortfolioStatus.SUSPENDED
        self._record_state_event("portfolio.suspended")

    def close(self) -> None:
        """Close portfolio and reject new transactions and positions."""
        self.status = PortfolioStatus.CLOSED
        self._record_state_event("portfolio.closed")

    def add_position(self, position: Position) -> None:
        """Add a position if portfolio is open and business key is unique."""
        self._ensure_not_closed()

        new_key = position.business_key()
        if any(existing.business_key() == new_key for existing in self.positions):
            raise DuplicatePositionError("Duplicate position business key is not allowed.")

        self.positions.append(position)
        self._record_event(
            PositionAdded.from_payload(
                aggregate_id=str(self.portfolio_id),
                payload={
                    "position_id": str(position.position_id),
                    "isin": position.isin.value,
                    "settlement_date": position.settlement_date.date.isoformat(),
                },
            )
        )

    def remove_position(self, position_id) -> None:
        """Remove a position by id and emit a domain event."""
        for index, position in enumerate(self.positions):
            if position.position_id == position_id:
                removed = self.positions.pop(index)
                self._record_event(
                    PositionRemoved.from_payload(
                        aggregate_id=str(self.portfolio_id),
                        payload={
                            "position_id": str(removed.position_id),
                            "isin": removed.isin.value,
                        },
                    )
                )
                return

        raise PositionNotFoundError("Position not found in portfolio.")

    def register_transaction(self, transaction: Transaction) -> None:
        """Register transaction against this portfolio aggregate."""
        self._ensure_not_closed()

        if transaction.portfolio_id != self.portfolio_id:
            raise ValueError("Transaction portfolio id does not match aggregate id.")

        self.transactions.append(transaction)
        self._record_event(
            TransactionRegistered.from_payload(
                aggregate_id=str(self.portfolio_id),
                payload={
                    "transaction_id": str(transaction.transaction_id),
                    "transaction_type": transaction.transaction_type.value,
                    "position_id": str(transaction.position_id),
                    "net_amount": str(transaction.net_amount.amount),
                    "currency": transaction.currency.value,
                },
            )
        )

    def total_nominal_value(self) -> Money:
        """Calculate total portfolio nominal value in base currency."""
        return PortfolioCalculationService.portfolio_nominal_value(
            self.positions, self.base_currency
        )

    def total_market_value(self) -> Money:
        """Calculate total portfolio market value in base currency."""
        return PortfolioCalculationService.portfolio_market_value(
            self.positions, self.base_currency
        )

    def total_book_value(self) -> Money:
        """Calculate total portfolio book value in base currency."""
        return PortfolioCalculationService.portfolio_book_value(self.positions, self.base_currency)

    def unrealized_gain_or_loss(self) -> Money:
        """Calculate unrealized portfolio gain or loss."""
        return PortfolioCalculationService.unrealized_gain_or_loss(
            self.positions, self.base_currency
        )

    def weighted_yield(self) -> Decimal:
        """Calculate weighted average yield in percentage points."""
        return PortfolioCalculationService.weighted_average_yield(
            self.positions, self.base_currency
        )

    def weighted_duration(self) -> Decimal:
        """Calculate weighted average duration."""
        return PortfolioCalculationService.weighted_average_duration(
            self.positions, self.base_currency
        )

    def weighted_convexity(self) -> Decimal:
        """Calculate weighted average convexity."""
        return PortfolioCalculationService.weighted_average_convexity(
            self.positions, self.base_currency
        )

    def pull_domain_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events."""
        events = list(self._events)
        self._events.clear()
        return events

    def _ensure_not_closed(self) -> None:
        """Ensure portfolio is not closed before mutation."""
        if self.status == PortfolioStatus.CLOSED:
            raise PortfolioClosedError(
                "Closed portfolio cannot accept new positions or transactions."
            )

    def _record_state_event(self, event_type: str) -> None:
        """Record generic state transition event."""
        self._record_event(
            DomainEvent.create(
                aggregate_id=str(self.portfolio_id),
                event_type=event_type,
                payload={"status": self.status.value},
            )
        )

    def _record_event(self, event: DomainEvent) -> None:
        """Store domain event for later publication."""
        self._events.append(event)
