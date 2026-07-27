"""Portfolio repository abstraction."""

from abc import ABC, abstractmethod

from src.aip.domain.portfolio.entities.portfolio import Portfolio
from src.aip.domain.portfolio.value_objects.portfolio_id import PortfolioId


class PortfolioRepository(ABC):
    """Repository contract for portfolio aggregate persistence."""

    @abstractmethod
    def add(self, portfolio: Portfolio) -> None:
        """Persist a new portfolio aggregate."""
        ...

    @abstractmethod
    def update(self, portfolio: Portfolio) -> None:
        """Persist changes of an existing portfolio aggregate."""
        ...

    @abstractmethod
    def get_by_id(self, portfolio_id: PortfolioId) -> Portfolio | None:
        """Retrieve portfolio by identifier."""
        ...

    @abstractmethod
    def get_by_name(self, name: str) -> Portfolio | None:
        """Retrieve portfolio by business name."""
        ...

    @abstractmethod
    def list_all(self) -> list[Portfolio]:
        """List all portfolio aggregates."""
        ...

    @abstractmethod
    def list_active(self) -> list[Portfolio]:
        """List active portfolio aggregates."""
        ...

    @abstractmethod
    def exists(self, portfolio_id: PortfolioId) -> bool:
        """Check if portfolio exists."""
        ...

    @abstractmethod
    def delete(self, portfolio_id: PortfolioId) -> None:
        """Delete portfolio by identifier."""
        ...
