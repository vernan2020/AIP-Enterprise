from __future__ import annotations

from abc import ABC, abstractmethod

from aip.domain.instruments.base.financial_instrument import FinancialInstrument


class InstrumentRepository(ABC):
    """Repository abstraction for instrument aggregates."""

    @abstractmethod
    def add(self, instrument: FinancialInstrument) -> None:
        """Persist a new instrument."""

    @abstractmethod
    def update(self, instrument: FinancialInstrument) -> None:
        """Persist changes to an existing instrument."""

    @abstractmethod
    def get_by_isin(self, isin: str) -> FinancialInstrument | None:
        """Get an instrument by ISIN."""

    @abstractmethod
    def list_all(self) -> list[FinancialInstrument]:
        """List all instruments."""
