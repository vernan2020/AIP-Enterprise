"""Position entity implementation."""

from dataclasses import dataclass
from datetime import datetime, timezone

from src.aip.domain.portfolio.enums.position_status import PositionStatus
from src.aip.domain.portfolio.enums.valuation_source import ValuationSource
from src.aip.domain.portfolio.exceptions import InvalidPositionError
from src.aip.domain.portfolio.value_objects.acquisition_cost import AcquisitionCost
from src.aip.domain.portfolio.value_objects.book_value import BookValue
from src.aip.domain.portfolio.value_objects.convexity import Convexity
from src.aip.domain.portfolio.value_objects.duration import Duration
from src.aip.domain.portfolio.value_objects.instrument_name import InstrumentName
from src.aip.domain.portfolio.value_objects.isin import ISIN
from src.aip.domain.portfolio.value_objects.market_value import MarketValue
from src.aip.domain.portfolio.value_objects.nominal_value import NominalValue
from src.aip.domain.portfolio.value_objects.position_id import PositionId
from src.aip.domain.portfolio.value_objects.quantity import Quantity
from src.aip.domain.portfolio.value_objects.settlement_date import SettlementDate
from src.aip.domain.portfolio.value_objects.yield_rate import YieldRate
from src.aip.shared.money import Currency


@dataclass(slots=True)
class Position:
    """Represents a portfolio holding position entity."""

    position_id: PositionId
    isin: ISIN
    instrument_name: InstrumentName
    currency: Currency
    quantity: Quantity
    nominal_value: NominalValue
    acquisition_cost: AcquisitionCost
    book_value: BookValue
    market_value: MarketValue
    yield_rate: YieldRate
    duration: Duration
    convexity: Convexity
    settlement_date: SettlementDate
    status: PositionStatus
    valuation_source: ValuationSource
    last_valuation_timestamp: datetime

    def __post_init__(self) -> None:
        self._validate_currency_consistency()

    @classmethod
    def create(
        cls,
        position_id: PositionId,
        isin: ISIN,
        instrument_name: InstrumentName,
        currency: Currency,
        quantity: Quantity,
        nominal_value: NominalValue,
        acquisition_cost: AcquisitionCost,
        book_value: BookValue,
        market_value: MarketValue,
        yield_rate: YieldRate,
        duration: Duration,
        convexity: Convexity,
        settlement_date: SettlementDate,
        valuation_source: ValuationSource,
    ) -> "Position":
        """Create a new open position with validated invariants."""
        return cls(
            position_id=position_id,
            isin=isin,
            instrument_name=instrument_name,
            currency=currency,
            quantity=quantity,
            nominal_value=nominal_value,
            acquisition_cost=acquisition_cost,
            book_value=book_value,
            market_value=market_value,
            yield_rate=yield_rate,
            duration=duration,
            convexity=convexity,
            settlement_date=settlement_date,
            status=PositionStatus.OPEN,
            valuation_source=valuation_source,
            last_valuation_timestamp=datetime.now(timezone.utc),
        )

    def business_key(self) -> tuple[str, str, str]:
        """Return unique business key used to avoid duplicates in portfolio."""
        return (
            self.isin.value,
            self.settlement_date.date.isoformat(),
            self.currency.value,
        )

    def update_market_valuation(
        self,
        market_value: MarketValue,
        valuation_source: ValuationSource,
        valued_at: datetime,
    ) -> None:
        """Update market valuation and source metadata."""
        self._ensure_open()
        if market_value.currency != self.currency:
            raise InvalidPositionError("Market value currency must match position currency.")
        self.market_value = market_value
        self.valuation_source = valuation_source
        self.last_valuation_timestamp = valued_at

    def update_book_value(self, book_value: BookValue, valued_at: datetime) -> None:
        """Update accounting book value."""
        self._ensure_open()
        if book_value.currency != self.currency:
            raise InvalidPositionError("Book value currency must match position currency.")
        self.book_value = book_value
        self.last_valuation_timestamp = valued_at

    def update_yield(self, yield_rate: YieldRate, valued_at: datetime) -> None:
        """Update yield metric."""
        self._ensure_open()
        self.yield_rate = yield_rate
        self.last_valuation_timestamp = valued_at

    def update_duration(self, duration: Duration, valued_at: datetime) -> None:
        """Update duration metric."""
        self._ensure_open()
        self.duration = duration
        self.last_valuation_timestamp = valued_at

    def update_convexity(self, convexity: Convexity, valued_at: datetime) -> None:
        """Update convexity metric."""
        self._ensure_open()
        self.convexity = convexity
        self.last_valuation_timestamp = valued_at

    def close_position(self) -> None:
        """Close position and prevent further valuation updates."""
        self.status = PositionStatus.CLOSED
        self.last_valuation_timestamp = datetime.now(timezone.utc)

    def _ensure_open(self) -> None:
        """Ensure position is open before allowing updates."""
        if self.status == PositionStatus.CLOSED:
            raise InvalidPositionError("Closed positions cannot be updated.")

    def _validate_currency_consistency(self) -> None:
        """Validate that all monetary value objects use the same currency."""
        if self.nominal_value.currency != self.currency:
            raise InvalidPositionError("Nominal value currency must match position currency.")
        if self.acquisition_cost.currency != self.currency:
            raise InvalidPositionError("Acquisition cost currency must match position currency.")
        if self.book_value.currency != self.currency:
            raise InvalidPositionError("Book value currency must match position currency.")
        if self.market_value.currency != self.currency:
            raise InvalidPositionError("Market value currency must match position currency.")
