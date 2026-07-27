# AIP Enterprise - AI Development Standards

**Version:** 1.0  
**Last Updated:** 2026-07-27  
**Status:** Mandatory

---

## 1. Project Philosophy

### Purpose

AIP Enterprise is an **enterprise treasury and investment management platform** designed to provide comprehensive portfolio management, asset allocation, and investment performance analytics for institutional investors. The platform serves as the central system for managing complex multi-asset portfolios, executing investment strategies, and ensuring regulatory compliance in the financial services industry.

### Quality Priorities

The AIP Enterprise project prioritizes the following principles, in order of importance:

1. **Maintainability** - Code must be easy to understand, modify, and extend by future developers
2. **Readability** - Code must be clear and self-documenting through meaningful names and structure
3. **Traceability** - Every transaction, calculation, and decision must be auditable and traceable
4. **Testability** - Code must be designed to be testable with comprehensive test coverage
5. **Auditability** - The system must support complete audit trails for regulatory compliance
6. **Financial Accuracy** - All calculations must be precise, reproducible, and verified
7. **Performance** - The system must respond efficiently to user actions and batch operations
8. **Regulatory Compliance** - The system must support regulatory requirements and audit procedures

### Core Principle

**Code quality is always more important than implementation speed.**

Quality software is cheaper to maintain, safer to extend, and more trustworthy in financial applications. Rushing implementation to meet deadlines leads to technical debt, bugs, security vulnerabilities, and ultimately higher costs.

---

## 2. Architecture

### Mandatory Architectural Patterns

Every module in AIP Enterprise must follow these mandatory architectural patterns:

#### **Clean Architecture**
- Separation of concerns into layers: UI → Application → Domain → Infrastructure
- Dependencies point inward toward the domain layer
- Business logic isolated from technical details
- Framework independence and testability

#### **Domain Driven Design (DDD)**
- Rich domain models that capture business rules
- Ubiquitous language throughout the codebase
- Bounded contexts with clear boundaries
- Domain events for cross-context communication
- Aggregates as transaction boundaries

#### **SOLID Principles**
- **Single Responsibility Principle**: Each class has one reason to change
- **Open/Closed Principle**: Open for extension, closed for modification
- **Liskov Substitution Principle**: Subtypes must be substitutable for base types
- **Interface Segregation Principle**: Clients should depend on specific interfaces
- **Dependency Inversion Principle**: Depend on abstractions, not concretions

#### **Repository Pattern**
- Data access abstraction through repositories
- Repositories encapsulate data retrieval logic
- Business logic never touches database queries directly
- Support for swapping implementations (in-memory for tests, SQL for production)

#### **Dependency Injection**
- All dependencies injected through constructors
- No service locator pattern
- Use of IoC container for managing service lifetimes
- Explicit dependency declaration

#### **CQRS (Command Query Responsibility Segregation)**
- Separate read and write models when beneficial
- Optimize read performance independently from write operations
- Implement read repositories for complex queries
- Command handlers for state-changing operations

#### **Unit of Work Pattern**
- Transaction management across multiple repositories
- Atomic operations across multiple aggregates (when appropriate)
- Change tracking and identity mapping
- Batch operations optimization

#### **Domain Events**
- Communication between aggregates through domain events
- Event sourcing for audit trails
- Eventual consistency between bounded contexts
- Observable business processes

#### **Value Objects**
- Immutable objects representing concepts without identity
- Equality based on value, not reference
- Self-validating with invariant enforcement
- Type-safe representations of business concepts

#### **Entities**
- Objects with persistent identity
- Mutable state representing business entities
- Business rules enforced within entities
- Ownership and lifecycle management

#### **Aggregate Roots**
- Entry points to aggregates
- Enforce invariants across aggregate boundaries
- Manage consistency of child entities
- Transaction boundaries for persistence

#### **Application Services**
- Orchestration of business operations
- Transaction management
- Cross-cutting concerns (logging, error handling)
- Never contain business logic (logic belongs in domain)

#### **Infrastructure Services**
- Technical implementations: database, file system, messaging
- Abstracted behind interfaces defined in the domain layer
- Testable through mock implementations
- Swappable for different environments

#### **Design Patterns - Always Use When Appropriate**
- **Factory Pattern**: Creating complex objects or families of objects
- **Strategy Pattern**: Runtime algorithm selection
- **Builder Pattern**: Constructing complex objects step-by-step
- **Adapter Pattern**: Bridging incompatible interfaces
- **Decorator Pattern**: Adding behavior dynamically
- **Chain of Responsibility**: Processing chains (logging, validation)

---

## 3. Folder Structure

### Official Project Structure

```
aip-enterprise/
│
├── src/
│   │
│   ├── aip/
│   │   │
│   │   ├── core/
│   │   │   ├── domain/              # Domain models, entities, value objects
│   │   │   │   ├── exceptions.py    # Domain exceptions
│   │   │   │   ├── events.py        # Domain events
│   │   │   │   └── [bounded_context]/
│   │   │   │       ├── models.py
│   │   │   │       ├── repositories/
│   │   │   │       │   └── abstractions.py
│   │   │   │       └── services.py
│   │   │   │
│   │   │   ├── application/         # Application layer (CQRS, use cases)
│   │   │   │   ├── commands/
│   │   │   │   ├── queries/
│   │   │   │   ├── handlers/
│   │   │   │   ├── dto/
│   │   │   │   └── services.py
│   │   │   │
│   │   │   ├── infrastructure/      # Technical implementations
│   │   │   │   ├── database/
│   │   │   │   │   ├── models.py
│   │   │   │   │   ├── repositories/
│   │   │   │   │   └── migrations/
│   │   │   │   ├── logging/
│   │   │   │   ├── messaging/
│   │   │   │   ├── cache/
│   │   │   │   └── di/              # Dependency injection
│   │   │   │
│   │   │   └── di/                  # Dependency Injection Framework
│   │   │       ├── container.py
│   │   │       ├── lifetimes.py
│   │   │       └── exceptions.py
│   │   │
│   │   ├── ui/                      # User Interface Layer
│   │   │   ├── views/
│   │   │   ├── controllers/
│   │   │   ├── components/
│   │   │   └── main_window.py
│   │   │
│   │   └── shared/                  # Shared utilities across layers
│   │       ├── constants.py
│   │       ├── exceptions.py
│   │       ├── utilities/
│   │       └── types.py
│   │
│   └── main.py                      # Application entry point
│
├── tests/
│   ├── unit/                        # Unit tests
│   │   ├── core/
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   └── infrastructure/
│   │   └── ui/
│   │
│   ├── integration/                 # Integration tests
│   │   ├── repositories/
│   │   ├── services/
│   │   └── workflows/
│   │
│   ├── e2e/                         # End-to-end tests
│   │   ├── treasury/
│   │   └── portfolio/
│   │
│   ├── conftest.py
│   └── fixtures/
│
├── docs/
│   ├── engineering/                 # Engineering standards
│   │   ├── AI_DEVELOPMENT_STANDARD.md
│   │   ├── ARCHITECTURE.md
│   │   └── DATABASE_SCHEMA.md
│   │
│   ├── domain/                      # Domain documentation
│   │   ├── TREASURY_CONCEPTS.md
│   │   └── INVESTMENT_THEORY.md
│   │
│   └── api/                         # API documentation
│       └── README.md
│
├── config/
│   ├── application.yaml
│   ├── database.yaml
│   ├── logging.yaml
│   └── [environment].yaml
│
├── scripts/
│   ├── install.sh
│   ├── run.sh
│   ├── test.sh
│   └── migrations.sh
│
├── pyproject.toml
├── setup.py
├── pytest.ini
├── .gitignore
├── README.md
└── LICENSE.md
```

### Folder Structure Rules

1. **Never break the layer structure** - UI should not import from domain, infrastructure should not contain business logic
2. **One bounded context per folder** - Keep related domain concepts together
3. **Test mirrors source structure** - `tests/unit/core/domain/` mirrors `src/aip/core/domain/`
4. **No circular dependencies** - Use dependency injection to break cycles
5. **Clear ownership** - Each folder has clear responsibility

---

## 4. Python Standards

### Language Version and Requirements

- **Minimum Python Version**: 3.13+
- **Type Hints**: Mandatory on all public functions and classes
- **Dataclasses**: Use whenever representing data structures
- **Composition**: Prefer composition over inheritance

### Type Hints - Mandatory

```python
# ✓ Correct - Full type hints
def calculate_portfolio_value(
    assets: list[Asset],
    market_prices: dict[str, Decimal],
) -> Decimal:
    """Calculate total portfolio value."""
    total: Decimal = Decimal("0")
    for asset in assets:
        total += asset.quantity * market_prices[asset.ticker]
    return total

# ✗ Wrong - Missing type hints
def calculate_portfolio_value(assets, market_prices):
    total = Decimal("0")
    for asset in assets:
        total += asset.quantity * market_prices[asset.ticker]
    return total
```

### Dataclasses

```python
from dataclasses import dataclass
from decimal import Decimal

# ✓ Correct - Using dataclass
@dataclass(frozen=True)
class Position:
    """A portfolio position."""
    ticker: str
    quantity: Decimal
    purchase_price: Decimal

# ✗ Wrong - Manual class with mutable defaults
class Position:
    def __init__(self, ticker, quantity, purchase_price=[]):
        self.ticker = ticker
        self.quantity = quantity
        self.purchase_price = purchase_price
```

### Never Use Mutable Default Arguments

```python
# ✓ Correct
def add_position(positions: list[Position] | None = None) -> list[Position]:
    if positions is None:
        positions = []
    return positions

# ✗ Wrong - Mutable default argument
def add_position(positions: list[Position] = []) -> list[Position]:
    return positions
```

### Composition Over Inheritance

```python
# ✓ Correct - Composition
class Portfolio:
    def __init__(self, positions: list[Position]) -> None:
        self._positions = positions

# ✗ Wrong - Deep inheritance hierarchy
class BasePortfolio:
    pass

class TaxablePortfolio(BasePortfolio):
    pass

class TaxDeferredPortfolio(TaxablePortfolio):
    pass
```

### Avoid Global State

```python
# ✓ Correct - Dependency injection
class PortfolioService:
    def __init__(self, repository: PortfolioRepository) -> None:
        self._repository = repository

# ✗ Wrong - Global state
_PORTFOLIO_REPOSITORY = None

def get_portfolio():
    global _PORTFOLIO_REPOSITORY
    return _PORTFOLIO_REPOSITORY.fetch()
```

### Use pathlib, Not os.path

```python
from pathlib import Path

# ✓ Correct
config_path = Path(__file__).parent / "config" / "app.yaml"
with open(config_path) as f:
    config = f.read()

# ✗ Wrong
import os
config_path = os.path.join(os.path.dirname(__file__), "config", "app.yaml")
```

### Use Enums, Not String Constants

```python
from enum import Enum

# ✓ Correct
class PortfolioStatus(Enum):
    """Portfolio status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"

portfolio.status = PortfolioStatus.ACTIVE

# ✗ Wrong
portfolio.status = "active"
if portfolio.status == "active":
    pass
```

### Code Length Limits

| Item | Maximum | Rationale |
|------|---------|-----------|
| **Function length** | 40 lines | Encourages single responsibility |
| **Class length** | 300 lines | Prevents monolithic classes |
| **File length** | 500 lines | Improves navigability |
| **Cyclomatic complexity** | 10 | Maintains testability |
| **Parameter count** | 4 | Use dependency injection for more |
| **Line length** | 100 characters | Improves readability |

```python
# ✓ Correct - Under 40 lines
def calculate_accrued_interest(
    principal: Decimal,
    annual_rate: Decimal,
    days_elapsed: int,
    day_count_convention: DayCountConvention,
) -> Decimal:
    """Calculate accrued interest on a bond position."""
    year_fraction = day_count_convention.calculate_year_fraction(days_elapsed)
    accrued = principal * annual_rate * year_fraction
    return accrued.quantize(Decimal("0.01"))

# ✗ Wrong - Over 40 lines
def calculate_accrued_interest(principal, annual_rate, days_elapsed, ...):
    # Too much logic, should be broken into smaller functions
    ...
```

---

## 5. Documentation

### Google Style Docstrings - Mandatory

Every public class and method must include Google-style docstrings. Docstrings are not optional.

#### Class Docstring

```python
class Portfolio:
    """Represents an investment portfolio.
    
    A portfolio contains multiple positions in various securities. It tracks
    the overall allocation, value, and performance of investments.
    
    Attributes:
        name: The portfolio name.
        owner: The portfolio owner.
        positions: List of positions in the portfolio.
        currency: The base currency for the portfolio.
    """
    
    def __init__(
        self,
        name: str,
        owner: str,
        positions: list[Position] | None = None,
        currency: str = "USD",
    ) -> None:
        """Initialize a portfolio.
        
        Args:
            name: The portfolio name.
            owner: The portfolio owner identifier.
            positions: Initial positions. Defaults to empty list.
            currency: Base currency code. Defaults to "USD".
        """
        self.name = name
        self.owner = owner
        self._positions = positions or []
        self.currency = currency
```

#### Method Docstring

```python
def calculate_total_value(self) -> Decimal:
    """Calculate the total market value of the portfolio.
    
    Returns the sum of all position values at current market prices.
    Uses Decimal arithmetic to maintain precision for financial calculations.
    
    Returns:
        The total portfolio value in the portfolio's base currency.
        
    Raises:
        ValueError: If market prices are not available for any position.
        
    Example:
        >>> portfolio = Portfolio("My Portfolio", "user123")
        >>> portfolio.add_position(Position("AAPL", Decimal("100")))
        >>> value = portfolio.calculate_total_value()
        >>> print(value)
        150000.00
    """
    total = Decimal("0")
    for position in self._positions:
        total += position.calculate_value()
    return total
```

### Documentation Requirements

| Item | Requirement |
|------|-------------|
| **Public Classes** | Complete docstring with purpose, attributes, and examples |
| **Public Methods** | Args, Returns, Raises, and Example sections |
| **Parameters** | Type and purpose description |
| **Return values** | Type and description of what is returned |
| **Exceptions** | All exceptions that can be raised |
| **Examples** | Real-world usage examples for complex methods |
| **Module docstring** | Module purpose and key exports |

### Example - Complete Documentation

```python
"""Portfolio management module.

This module provides core portfolio management functionality including
position tracking, valuation, and performance calculations.

Classes:
    Portfolio: Main portfolio aggregate root.
    Position: Individual security position.
    PortfolioService: Application service for portfolio operations.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import date

@dataclass(frozen=True)
class Position:
    """Represents a single security position in a portfolio.
    
    Attributes:
        ticker: The security ticker symbol.
        quantity: The number of shares held.
        purchase_price: The purchase price per share.
        purchase_date: The date the position was purchased.
    """
    ticker: str
    quantity: Decimal
    purchase_price: Decimal
    purchase_date: date
    
    def calculate_value(self, current_price: Decimal) -> Decimal:
        """Calculate the current market value of this position.
        
        Args:
            current_price: The current market price per share.
            
        Returns:
            The current total market value of the position.
            
        Raises:
            ValueError: If current_price is negative.
            
        Example:
            >>> position = Position("AAPL", Decimal("100"), Decimal("150"), date(2024, 1, 1))
            >>> value = position.calculate_value(Decimal("180"))
            >>> print(value)
            18000
        """
        if current_price < 0:
            raise ValueError("Current price cannot be negative")
        return self.quantity * current_price
```

---

## 6. Testing

### Test Coverage Minimum: 90%

Every module must achieve at least 90% test coverage. This is verified through continuous integration.

```bash
# Run tests with coverage report
pytest --cov=src --cov-report=html --cov-fail-under=90

# Check coverage for specific module
pytest --cov=src.aip.core.domain --cov-report=term-missing
```

### Testing Rules

1. **Every bug fixed must include a regression test** - Prevents the same bug from recurring
2. **All Value Objects require unit tests** - Test immutability, equality, validation
3. **Repositories require integration tests** - Test actual database operations
4. **Domain services require unit tests** - Mock repositories, test business logic
5. **Application services require integration tests** - Test orchestration and transactions
6. **Use fixtures for complex test data** - Reusable test data setup

### Test Structure

```
tests/
├── unit/                          # Unit tests (90% of tests)
│   └── core/
│       ├── domain/
│       │   ├── test_portfolio.py
│       │   ├── test_position.py
│       │   └── test_value_objects.py
│       └── application/
│           └── test_portfolio_service.py
│
├── integration/                   # Integration tests (8% of tests)
│   ├── repositories/
│   │   └── test_portfolio_repository.py
│   └── services/
│       └── test_portfolio_service_integration.py
│
└── e2e/                          # End-to-end tests (2% of tests)
    └── test_portfolio_workflow.py
```

### Testing Example

```python
import pytest
from decimal import Decimal
from datetime import date
from src.aip.core.domain.portfolio import Portfolio, Position


class TestPortfolio:
    """Tests for Portfolio domain model."""
    
    @pytest.fixture
    def portfolio(self) -> Portfolio:
        """Create a test portfolio."""
        return Portfolio(
            name="Test Portfolio",
            owner="test_user",
            currency="USD",
        )
    
    @pytest.fixture
    def position(self) -> Position:
        """Create a test position."""
        return Position(
            ticker="AAPL",
            quantity=Decimal("100"),
            purchase_price=Decimal("150"),
            purchase_date=date(2024, 1, 1),
        )
    
    def test_portfolio_creation(self, portfolio: Portfolio) -> None:
        """Test portfolio can be created."""
        assert portfolio.name == "Test Portfolio"
        assert portfolio.owner == "test_user"
        assert portfolio.currency == "USD"
    
    def test_position_value_calculation(self, position: Position) -> None:
        """Test position value calculation."""
        current_price = Decimal("180")
        value = position.calculate_value(current_price)
        assert value == Decimal("18000")
    
    def test_negative_price_raises_error(self, position: Position) -> None:
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            position.calculate_value(Decimal("-100"))
        assert "negative" in str(exc_info.value).lower()


class TestPortfolioValueObjects:
    """Tests for Portfolio value objects."""
    
    def test_position_immutability(self) -> None:
        """Test that Position is immutable."""
        position = Position(
            ticker="AAPL",
            quantity=Decimal("100"),
            purchase_price=Decimal("150"),
            purchase_date=date(2024, 1, 1),
        )
        
        with pytest.raises(AttributeError):
            position.quantity = Decimal("200")
    
    def test_position_equality(self) -> None:
        """Test Position equality based on value."""
        pos1 = Position("AAPL", Decimal("100"), Decimal("150"), date(2024, 1, 1))
        pos2 = Position("AAPL", Decimal("100"), Decimal("150"), date(2024, 1, 1))
        
        assert pos1 == pos2
```

---

## 7. Logging

### Logging Framework: Loguru

All logging must use **Loguru**. Never use `print()` for any output that should be logged.

### Logging Setup

```python
from loguru import logger

# Configure logging
logger.add(
    "logs/{time:YYYY-MM-DD}/app.log",
    rotation="00:00",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)
```

### Log Levels

| Level | Purpose | Example |
|-------|---------|---------|
| **DEBUG** | Detailed diagnostic information | Variable values, loop iterations |
| **INFO** | General informational messages | Application startup, operations completed |
| **WARNING** | Warning messages for unexpected situations | Deprecated API usage, performance issues |
| **ERROR** | Error messages for recoverable errors | Failed database query, invalid input |
| **CRITICAL** | Critical system errors | Database connection lost, data corruption |

### Logging Rules

1. **No print() statements** - Use logger instead
2. **Log at appropriate levels** - Debug for details, Info for operations, Error for failures
3. **Include context in logs** - Use structured logging with context
4. **Never log sensitive data** - No passwords, API keys, personal information
5. **Use {} formatting, not f-strings** - Allows conditional logging performance optimization

### Logging Examples

```python
from loguru import logger

class PortfolioService:
    """Application service for portfolio operations."""
    
    def create_portfolio(self, name: str, owner: str) -> Portfolio:
        """Create a new portfolio.
        
        Args:
            name: Portfolio name.
            owner: Portfolio owner.
            
        Returns:
            The created portfolio.
        """
        logger.debug("Creating portfolio: name={}, owner={}", name, owner)
        
        try:
            portfolio = Portfolio(name=name, owner=owner)
            logger.info("Portfolio created successfully: portfolio_id={}", portfolio.id)
            return portfolio
        except ValueError as e:
            logger.error("Failed to create portfolio: {}", str(e))
            raise
    
    def delete_portfolio(self, portfolio_id: str) -> None:
        """Delete a portfolio.
        
        Args:
            portfolio_id: The portfolio to delete.
        """
        logger.debug("Deleting portfolio: portfolio_id={}", portfolio_id)
        
        try:
            self._repository.delete(portfolio_id)
            logger.info("Portfolio deleted: portfolio_id={}", portfolio_id)
        except Exception as e:
            logger.error("Failed to delete portfolio: portfolio_id={}, error={}", portfolio_id, str(e))
            raise
    
    def calculate_performance(self, portfolio_id: str) -> Decimal:
        """Calculate portfolio performance.
        
        Args:
            portfolio_id: The portfolio to analyze.
            
        Returns:
            The performance percentage.
        """
        logger.debug("Calculating performance for portfolio: portfolio_id={}", portfolio_id)
        
        portfolio = self._repository.get(portfolio_id)
        if not portfolio:
            logger.warning("Portfolio not found: portfolio_id={}", portfolio_id)
            return Decimal("0")
        
        performance = portfolio.calculate_performance()
        logger.info("Performance calculated: portfolio_id={}, performance={}%", 
                   portfolio_id, performance)
        return performance

# ✗ Wrong - Using print()
print("Portfolio created")
print(f"Portfolio ID: {portfolio.id}")

# ✗ Wrong - Logging sensitive data
logger.info("User authenticated: username={}, password={}", username, password)
```

---

## 8. Error Handling

### Error Handling Rules

1. **Never swallow exceptions** - Every exception must be handled or re-raised
2. **Raise domain-specific exceptions** - Use custom exception hierarchy
3. **Wrap infrastructure exceptions** - Don't expose raw database/API errors
4. **Never expose raw SQL errors** - Translate to business-relevant errors
5. **Always provide context** - Include relevant information in error messages

### Exception Hierarchy

```python
"""Domain exceptions."""

class DomainException(Exception):
    """Base exception for all domain errors."""
    pass

class PortfolioException(DomainException):
    """Base exception for portfolio-related errors."""
    pass

class PortfolioNotFoundError(PortfolioException):
    """Raised when a portfolio is not found."""
    def __init__(self, portfolio_id: str) -> None:
        super().__init__(f"Portfolio not found: {portfolio_id}")
        self.portfolio_id = portfolio_id

class InvalidPortfolioError(PortfolioException):
    """Raised when portfolio data is invalid."""
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid portfolio: {reason}")
        self.reason = reason

class InsufficientFundsError(PortfolioException):
    """Raised when portfolio has insufficient funds."""
    def __init__(self, required: Decimal, available: Decimal) -> None:
        super().__init__(
            f"Insufficient funds: required={required}, available={available}"
        )
        self.required = required
        self.available = available
```

### Error Handling Examples

```python
from loguru import logger

class PortfolioRepository:
    """Portfolio repository."""
    
    def get(self, portfolio_id: str) -> Portfolio:
        """Get a portfolio by ID.
        
        Args:
            portfolio_id: The portfolio ID.
            
        Returns:
            The portfolio.
            
        Raises:
            PortfolioNotFoundError: If portfolio not found.
            DatabaseError: If database operation fails.
        """
        logger.debug("Fetching portfolio: portfolio_id={}", portfolio_id)
        
        try:
            # Query database
            row = self._db.execute(
                "SELECT * FROM portfolios WHERE id = ?",
                (portfolio_id,)
            ).fetchone()
            
            if not row:
                raise PortfolioNotFoundError(portfolio_id)
            
            return self._map_to_portfolio(row)
            
        except PortfolioNotFoundError:
            # Re-raise domain exceptions
            raise
        except Exception as e:
            # Wrap infrastructure exceptions
            logger.error("Database error fetching portfolio: portfolio_id={}, error={}", 
                        portfolio_id, str(e))
            raise DatabaseError(
                f"Failed to fetch portfolio {portfolio_id}"
            ) from e

class PortfolioService:
    """Portfolio application service."""
    
    def transfer_funds(
        self,
        from_portfolio_id: str,
        to_portfolio_id: str,
        amount: Decimal,
    ) -> None:
        """Transfer funds between portfolios.
        
        Args:
            from_portfolio_id: Source portfolio.
            to_portfolio_id: Destination portfolio.
            amount: Amount to transfer.
            
        Raises:
            PortfolioNotFoundError: If portfolio not found.
            InsufficientFundsError: If source lacks funds.
        """
        logger.info("Transferring funds: from={}, to={}, amount={}", 
                   from_portfolio_id, to_portfolio_id, amount)
        
        try:
            # Fetch portfolios
            from_portfolio = self._repository.get(from_portfolio_id)
            to_portfolio = self._repository.get(to_portfolio_id)
            
            # Validate balance
            if from_portfolio.balance < amount:
                raise InsufficientFundsError(
                    required=amount,
                    available=from_portfolio.balance,
                )
            
            # Execute transfer
            from_portfolio.withdraw(amount)
            to_portfolio.deposit(amount)
            
            # Persist changes
            self._unit_of_work.commit()
            
            logger.info("Funds transferred successfully")
            
        except (PortfolioNotFoundError, InsufficientFundsError):
            # Re-raise domain exceptions
            raise
        except Exception as e:
            logger.error("Transfer failed: error={}", str(e))
            self._unit_of_work.rollback()
            raise
```

---

## 9. Financial Rules

### Absolutely Prohibited

These practices are **never permitted** under any circumstances:

| Prohibited | Reason | Location |
|-----------|--------|----------|
| **Financial calculations in UI** | UI is for presentation only, not computation | Never in views/controllers |
| **Financial calculations in JavaScript** | JavaScript cannot guarantee precision | Backend only |
| **Business logic in repositories** | Repositories are data access only | Belongs in domain/services |
| **Hidden formulas** | All calculations must be traceable | Every formula must be documented |

### Financial Calculation Rules

1. **Every calculation must be reproducible**
   - Same inputs must always produce same outputs
   - Use deterministic algorithms
   - Document all assumptions

2. **Every financial formula must include references**
   - Academic source (textbook, paper)
   - Industry standard (ISDA, SIFMA)
   - Regulatory requirement (SEC, FINRA)
   - Version and date of reference

3. **Use Decimal, never float**
   - `from decimal import Decimal`
   - Maintains precision for financial calculations
   - Always quantize to appropriate precision

4. **Always separate values**
   - Nominal value vs Market value
   - Accounting value vs Fair value
   - Book value vs Market value

### Financial Calculation Example

```python
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

class BondValuation(NamedTuple):
    """Bond valuation results."""
    dirty_price: Decimal      # Includes accrued interest
    clean_price: Decimal      # Excludes accrued interest
    accrued_interest: Decimal # Interest accrued since last coupon
    yield_to_maturity: Decimal


class BondService:
    """Bond valuation service.
    
    References:
    - Fixed Income Securities (Tuckman, 2012)
    - SIFMA Bond Pricing Standards
    """
    
    def calculate_bond_valuation(
        self,
        face_value: Decimal,
        coupon_rate: Decimal,
        years_to_maturity: Decimal,
        yield_to_maturity: Decimal,
        accrual_method: str = "ACTUAL/365",
    ) -> BondValuation:
        """Calculate bond valuation including accrued interest.
        
        Formula: Price = Sum of PV(Coupons) + PV(Principal)
        Where: PV = Payment / (1 + YTM)^n
        
        References:
        - Tuckman (2012): Fixed Income Analytics
        - FINRA Rule 4512 (Bond pricing)
        
        Args:
            face_value: Par value of the bond.
            coupon_rate: Annual coupon rate.
            years_to_maturity: Years until maturity.
            yield_to_maturity: Required yield.
            accrual_method: Day count convention (ACTUAL/365, 30/360, etc).
            
        Returns:
            Bond valuation with dirty price (includes accrued interest).
            
        Raises:
            ValueError: If any input is invalid.
        """
        # Validate inputs
        if face_value <= 0:
            raise ValueError("Face value must be positive")
        if coupon_rate < 0:
            raise ValueError("Coupon rate cannot be negative")
        if yield_to_maturity < 0:
            raise ValueError("Yield cannot be negative")
        
        # Calculate clean price (excludes accrued interest)
        annual_coupon = face_value * coupon_rate
        periods = int(years_to_maturity * 2)  # Semi-annual coupons
        ytm_period = yield_to_maturity / 2
        coupon_period = annual_coupon / 2
        
        # Sum of present value of coupons
        pv_coupons = Decimal("0")
        for period in range(1, periods + 1):
            pv_coupons += coupon_period / (1 + ytm_period) ** period
        
        # Present value of principal
        pv_principal = face_value / (1 + ytm_period) ** periods
        
        # Clean price (excludes accrued interest)
        clean_price = (pv_coupons + pv_principal).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        
        # Calculate accrued interest
        accrued_interest = self._calculate_accrued_interest(
            face_value,
            coupon_rate,
            accrual_method,
        )
        
        # Dirty price (includes accrued interest)
        dirty_price = (clean_price + accrued_interest).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )
        
        return BondValuation(
            dirty_price=dirty_price,
            clean_price=clean_price,
            accrued_interest=accrued_interest,
            yield_to_maturity=yield_to_maturity,
        )
    
    def _calculate_accrued_interest(
        self,
        face_value: Decimal,
        coupon_rate: Decimal,
        accrual_method: str,
    ) -> Decimal:
        """Calculate accrued interest since last coupon.
        
        References:
        - ISDA - Day Count Conventions
        - FINRA Rule 4512
        """
        # Implementation of day count convention
        pass
```

### Treasury Domain Requirements

The framework must support:

- ✓ Multiple currencies with exchange rates
- ✓ Settlement calendars (business day conventions)
- ✓ Day count conventions (ACTUAL/365, 30/360, etc)
- ✓ Business calendars (holiday schedules)
- ✓ Coupon schedules for fixed income
- ✓ Yield curve analysis
- ✓ Duration calculations (modified, effective, key-rate)
- ✓ High-Quality Liquid Assets (HQLA) classifications
- ✓ Liquidity metrics and coverage ratios
- ✓ Value at Risk (VaR) calculations
- ✓ Stress testing frameworks

---

## 10. Performance

### Performance Rules

1. **Prefer generators over lists**
   - Use generators for large data sets
   - Lazy evaluation reduces memory

2. **Avoid unnecessary copies**
   - Reuse objects when possible
   - Use references instead of deep copies

3. **Use lazy loading**
   - Don't load all data upfront
   - Load on demand

4. **Batch database operations**
   - Use bulk inserts/updates
   - Minimize round trips

5. **Cache expensive computations**
   - Cache calculated values
   - Invalidate cache appropriately

### Performance Examples

```python
# ✓ Correct - Using generators
def fetch_large_dataset() -> Generator[Portfolio, None, None]:
    """Fetch portfolios using generator for memory efficiency."""
    batch_size = 1000
    offset = 0
    
    while True:
        portfolios = self._repository.fetch(offset=offset, limit=batch_size)
        if not portfolios:
            break
        
        for portfolio in portfolios:
            yield portfolio
        
        offset += batch_size

# Process large dataset
for portfolio in fetch_large_dataset():
    process_portfolio(portfolio)  # Processed one at a time

# ✗ Wrong - Loading all data into memory
portfolios = self._repository.fetch_all()  # All 1 million records in memory
for portfolio in portfolios:
    process_portfolio(portfolio)

# ✓ Correct - Batch operations
def create_portfolios(names: list[str]) -> None:
    """Create multiple portfolios in a single batch operation."""
    portfolios = [Portfolio(name=name) for name in names]
    self._repository.create_batch(portfolios)  # Single INSERT statement

# ✗ Wrong - Individual operations
for name in names:
    portfolio = Portfolio(name=name)
    self._repository.create(portfolio)  # 1000 INSERT statements for 1000 portfolios
```

---

## 11. Security

### Security Rules

Never hardcode:
- ✗ Passwords
- ✗ API tokens
- ✗ Secrets
- ✗ Connection strings
- ✗ Private keys
- ✗ Encryption keys

Always use environment variables.

### Security Implementation

```python
from pathlib import Path
from os import environ

# ✓ Correct - Using environment variables
DATABASE_URL = environ.get("DATABASE_URL")
API_KEY = environ.get("API_KEY")
SECRET_KEY = environ.get("SECRET_KEY")

if not all([DATABASE_URL, API_KEY, SECRET_KEY]):
    raise ValueError("Missing required environment variables")

# ✗ Wrong - Hardcoded secrets
DATABASE_URL = "postgresql://user:password@localhost/aip"
API_KEY = "sk_live_1234567890abcdef"
SECRET_KEY = "my-secret-key-123"

# ✓ Correct - Configuration from environment
class Config:
    """Application configuration."""
    
    # Database
    DATABASE_URL: str = environ.get("DATABASE_URL", "")
    DATABASE_POOL_SIZE: int = int(environ.get("DATABASE_POOL_SIZE", "20"))
    
    # Security
    SECRET_KEY: str = environ.get("SECRET_KEY", "")
    API_KEY: str = environ.get("API_KEY", "")
    
    # Logging
    LOG_LEVEL: str = environ.get("LOG_LEVEL", "INFO")
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable not set")
        if not self.API_KEY:
            raise ValueError("API_KEY environment variable not set")

# .env file (never committed to git)
# DATABASE_URL=postgresql://user:password@localhost/aip
# SECRET_KEY=my-secret-key-production
# API_KEY=sk_live_1234567890abcdef
```

### .gitignore - Protect Secrets

```
# Environment variables
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
.pytest_cache/
.coverage

# Database
*.db
*.sqlite

# Logs
logs/
*.log
```

---

## 12. Code Review Checklist

Every pull request must pass this checklist before merging.

### Architecture Checklist

- [ ] Code follows Clean Architecture layers
- [ ] Dependencies point inward (toward domain)
- [ ] No circular dependencies
- [ ] Domain models contain business logic
- [ ] Infrastructure doesn't leak into domain
- [ ] Dependency injection used correctly
- [ ] No hard-coded dependencies

### Testing Checklist

- [ ] Tests cover new functionality
- [ ] Test coverage >= 90%
- [ ] Unit tests for domain logic
- [ ] Integration tests for repositories
- [ ] Tests are independent and repeatable
- [ ] No flaky tests
- [ ] Regression test added for bug fixes

### Documentation Checklist

- [ ] Google-style docstrings on all public methods
- [ ] Parameters documented with type and description
- [ ] Return values documented
- [ ] Exceptions documented (Raises section)
- [ ] Examples provided for complex methods
- [ ] README updated if API changed
- [ ] Comments explain "why", not "what"

### Logging Checklist

- [ ] No print() statements
- [ ] Appropriate log levels used
- [ ] No sensitive data logged
- [ ] Context included in log messages
- [ ] Log messages are informative

### Performance Checklist

- [ ] No unnecessary database queries
- [ ] Batch operations used for bulk work
- [ ] No N+1 query problems
- [ ] Large collections use generators
- [ ] Caching implemented where beneficial
- [ ] No unnecessary copies of large objects

### Security Checklist

- [ ] No hardcoded secrets
- [ ] Environment variables used for configuration
- [ ] No sensitive data in logs
- [ ] SQL injection prevented (parameterized queries)
- [ ] Input validation performed
- [ ] OWASP top 10 considered

### Type Hints Checklist

- [ ] All public methods have return type hints
- [ ] All parameters have type hints
- [ ] Complex types use type aliases
- [ ] Generic types properly parameterized
- [ ] Optional types use Optional or Union
- [ ] Type hints pass mypy static analysis

### Exception Handling Checklist

- [ ] Domain-specific exceptions used
- [ ] Infrastructure exceptions wrapped
- [ ] No exceptions swallowed silently
- [ ] Error messages are informative
- [ ] Finally blocks used for cleanup
- [ ] Resource management (context managers)

### Financial Rules Checklist

- [ ] No financial calculations in UI
- [ ] No financial calculations in JavaScript
- [ ] No business logic in repositories
- [ ] Decimal used for all money calculations
- [ ] Calculations are reproducible
- [ ] Formulas include references
- [ ] Nominal vs Market values separated

---

## 13. AI Development Rules

When generating code, the AI must follow these rules:

### Never Acceptable

- ✗ **Never generate placeholder implementations**
  ```python
  # WRONG - Placeholder code
  def calculate_portfolio_performance():
      # TODO: Implement performance calculation
      return Decimal("0")
  ```

- ✗ **Never generate TODO code**
  ```python
  # WRONG - TODO indicates incomplete work
  def fetch_historical_data():
      # TODO: Add database query
      pass
  ```

- ✗ **Never generate pass statements**
  ```python
  # WRONG - pass statement
  def validate_portfolio(portfolio):
      pass  # Should not exist in production code
  ```

- ✗ **Never generate mocked business logic**
  ```python
  # WRONG - Mocked logic
  def calculate_risk():
      return Decimal("5.0")  # Hardcoded for testing
  ```

### Always Required

- ✓ **Always produce production-ready code**
  - Complete implementation
  - No placeholders
  - Ready to deploy

- ✓ **Always include tests**
  - Unit tests for domain logic
  - Integration tests for repositories
  - Coverage >= 90%

- ✓ **Always include documentation**
  - Google-style docstrings
  - Type hints
  - Examples

- ✓ **Always explain architectural decisions**
  - Why this pattern was chosen
  - Trade-offs considered
  - Alternative approaches

### Generated Code Example

```python
"""Portfolio valuation service.

References:
- Markowitz Modern Portfolio Theory
- Sharpe Ratio (Sharpe, 1964)
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from loguru import logger

@dataclass(frozen=True)
class PortfolioMetrics:
    """Portfolio performance metrics.
    
    Attributes:
        total_value: Total market value of portfolio.
        daily_return: Daily return percentage.
        sharpe_ratio: Risk-adjusted return (Sharpe ratio).
    """
    total_value: Decimal
    daily_return: Decimal
    sharpe_ratio: Decimal


class PortfolioValuationService:
    """Service for portfolio valuation and metrics.
    
    References:
    - Modern Portfolio Theory (Markowitz, 1952)
    - Sharpe Ratio (Sharpe, 1964)
    """
    
    def __init__(self, repository: PortfolioRepository) -> None:
        """Initialize valuation service.
        
        Args:
            repository: Portfolio repository for data access.
        """
        self._repository = repository
    
    def calculate_portfolio_metrics(self, portfolio_id: str) -> PortfolioMetrics:
        """Calculate portfolio performance metrics.
        
        References:
        - Markowitz (1952): Modern Portfolio Theory
        - Sharpe (1964): The Sharpe Ratio
        
        Args:
            portfolio_id: The portfolio to analyze.
            
        Returns:
            Portfolio metrics including value and Sharpe ratio.
            
        Raises:
            PortfolioNotFoundError: If portfolio not found.
            ValueError: If metrics cannot be calculated.
            
        Example:
            >>> service = PortfolioValuationService(repo)
            >>> metrics = service.calculate_portfolio_metrics("port123")
            >>> print(metrics.sharpe_ratio)
            1.25
        """
        logger.debug("Calculating metrics for portfolio: portfolio_id={}", portfolio_id)
        
        try:
            # Fetch portfolio data
            portfolio = self._repository.get(portfolio_id)
            
            # Calculate total value
            total_value = self._calculate_total_value(portfolio)
            
            # Calculate daily return
            daily_return = self._calculate_daily_return(portfolio)
            
            # Calculate Sharpe ratio
            sharpe_ratio = self._calculate_sharpe_ratio(portfolio, daily_return)
            
            logger.info(
                "Metrics calculated: portfolio_id={}, total_value={}, sharpe_ratio={}",
                portfolio_id, total_value, sharpe_ratio
            )
            
            return PortfolioMetrics(
                total_value=total_value,
                daily_return=daily_return,
                sharpe_ratio=sharpe_ratio,
            )
            
        except PortfolioNotFoundError:
            raise
        except Exception as e:
            logger.error("Failed to calculate metrics: portfolio_id={}, error={}", 
                        portfolio_id, str(e))
            raise ValueError(f"Cannot calculate metrics for portfolio {portfolio_id}") from e
    
    def _calculate_total_value(self, portfolio: Portfolio) -> Decimal:
        """Calculate total market value of portfolio."""
        total = Decimal("0")
        for position in portfolio.positions:
            market_value = position.quantity * position.current_price
            total += market_value
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def _calculate_daily_return(self, portfolio: Portfolio) -> Decimal:
        """Calculate daily return percentage."""
        today_value = self._calculate_total_value(portfolio)
        previous_value = portfolio.previous_day_value
        
        if previous_value <= 0:
            return Decimal("0")
        
        daily_return = ((today_value - previous_value) / previous_value * 100)
        return daily_return.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    
    def _calculate_sharpe_ratio(self, portfolio: Portfolio, daily_return: Decimal) -> Decimal:
        """Calculate Sharpe ratio.
        
        Formula: Sharpe = (Return - RiskFree) / StdDev
        
        References:
        - Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium
        """
        # Get historical returns for standard deviation
        historical_returns = portfolio.get_historical_returns(days=252)  # One year
        
        if not historical_returns or len(historical_returns) < 2:
            return Decimal("0")
        
        # Calculate standard deviation
        std_dev = self._calculate_standard_deviation(historical_returns)
        
        if std_dev == 0:
            return Decimal("0")
        
        # Risk-free rate (could be parameterized)
        risk_free_rate = Decimal("0.02")  # 2% annual
        
        # Sharpe ratio = (annual return - risk free rate) / std dev
        sharpe = (daily_return * 252 - risk_free_rate) / std_dev
        
        return sharpe.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    
    def _calculate_standard_deviation(self, returns: list[Decimal]) -> Decimal:
        """Calculate standard deviation of returns."""
        if not returns:
            return Decimal("0")
        
        # Mean return
        mean = sum(returns) / len(returns)
        
        # Variance
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        
        # Standard deviation
        std_dev = variance.sqrt()
        
        return std_dev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

---

## 14. Treasury Domain Rules

Treasury systems have specific requirements to ensure accuracy and regulatory compliance.

### Core Treasury Requirements

#### Never Lose Precision

- Use `Decimal` for all monetary values
- Never use floating-point arithmetic for financial calculations
- Quantize to appropriate decimal places

#### Separate Value Types

- **Nominal Value** vs **Market Value**
  - Nominal: Face/par value
  - Market: Current market price

- **Accounting Value** vs **Fair Value**
  - Accounting: Book value per GAAP
  - Fair: Market-based valuation

```python
@dataclass
class BondPosition:
    """Bond position with multiple value representations."""
    nominal_value: Decimal  # Par value
    market_value: Decimal   # Market price
    accounting_value: Decimal  # Book value for financial statements
    fair_value: Decimal     # Fair market value for reporting
```

#### Multi-Currency Support

- Support multiple currencies
- Store exchange rates at transaction time
- Revalue positions at current rates
- Support historical rate lookups

```python
@dataclass
class MultiCurrencyPosition:
    """Position in foreign currency."""
    security: Security
    quantity: Decimal
    currency: str  # ISO 4217 code
    local_value: Decimal  # In currency
    home_value: Decimal   # Converted to home currency
```

#### Settlement Calendars

- Implement T+0, T+1, T+2 settlement rules
- Support holiday calendars per market
- Track settlement dates vs trade dates
- Handle month-end considerations

#### Day Count Conventions

Support standard day count conventions:
- ACTUAL/365
- ACTUAL/360
- ACTUAL/ACTUAL
- 30/360
- 30E/360

```python
from enum import Enum

class DayCountConvention(Enum):
    """Day count conventions for interest calculations."""
    ACTUAL_365 = "ACTUAL/365"
    ACTUAL_360 = "ACTUAL/360"
    ACTUAL_ACTUAL = "ACTUAL/ACTUAL"
    THIRTY_360 = "30/360"
    THIRTY_E_360 = "30E/360"
```

#### Business Calendars

- Define working days per market
- Holiday schedules
- Early close dates
- Trading hours validation

#### Coupon Schedules

- Fixed coupon frequency (semi-annual, annual, etc.)
- Next coupon date calculation
- Coupon date adjustments
- Ex-dividend considerations

#### Yield Curve Analysis

- Support multiple yield curves (Treasury, swap, corporate)
- Interpolation methods (linear, cubic spline, etc.)
- Forward curve calculation
- Spot curve construction

#### Duration Calculations

- **Modified Duration**: Interest rate sensitivity
- **Effective Duration**: Option-adjusted duration
- **Key Rate Duration**: Duration at specific maturities
- **DV01**: Dollar value of one basis point move

#### HQLA Classifications

High-Quality Liquid Assets classification per Basel III:
- Level 1 assets (0% haircut)
- Level 2A assets (15% haircut)
- Level 2B assets (25-50% haircut)
- Liquidity coverage ratio (LCR) calculations

#### Liquidity Metrics

- Bid-ask spreads
- Trading volumes
- Market depth
- Concentration limits
- Liquidity stress testing

#### Value at Risk (VaR)

- Parametric VaR
- Historical VaR
- Monte Carlo VaR
- Conditional VaR (CVaR)
- Incremental VaR

#### Stress Testing

- Parallel shift scenarios
- Twist scenarios (steepener/flattener)
- Butterfly scenarios
- Historical scenarios
- Hypothetical scenarios

---

## 15. Definition of Done

A module is **complete and ready for production** only when ALL of the following are true:

### ✓ Code Quality

- [ ] Code compiles without errors or warnings
- [ ] Code follows all style guidelines
- [ ] Code uses type hints on all public methods
- [ ] Code uses dataclasses where appropriate
- [ ] Code avoids mutable default arguments
- [ ] Code avoids global state
- [ ] Code uses pathlib for file operations
- [ ] Code uses enums instead of string constants

### ✓ Testing

- [ ] All tests pass (100% pass rate)
- [ ] Code coverage >= 90%
- [ ] Unit tests for all domain logic
- [ ] Integration tests for repositories
- [ ] No skipped or pending tests
- [ ] Regression test added for any bugs fixed
- [ ] Tests are independent and repeatable
- [ ] No flaky or timing-dependent tests

### ✓ Documentation

- [ ] All public classes have docstrings (Google style)
- [ ] All public methods have docstrings (Google style)
- [ ] All parameters documented with type and description
- [ ] All return values documented
- [ ] All exceptions documented in Raises section
- [ ] Examples provided for complex methods
- [ ] README updated if API changed
- [ ] Architecture decisions documented

### ✓ Logging

- [ ] No print() statements used
- [ ] Loguru configured appropriately
- [ ] Appropriate log levels used (DEBUG, INFO, WARNING, ERROR)
- [ ] No sensitive data in logs
- [ ] Context included in log messages
- [ ] Error conditions logged at ERROR level
- [ ] Success operations logged at INFO level

### ✓ Exception Handling

- [ ] Domain-specific exceptions defined and used
- [ ] Infrastructure exceptions wrapped in domain exceptions
- [ ] No exceptions swallowed silently
- [ ] Error messages are informative and include context
- [ ] Finally blocks used for resource cleanup
- [ ] Context managers used for resource management

### ✓ Performance

- [ ] No N+1 query problems
- [ ] Batch database operations used for bulk work
- [ ] Large collections use generators where appropriate
- [ ] No unnecessary database queries
- [ ] No unnecessary copies of large objects
- [ ] Caching implemented for expensive operations
- [ ] Query performance acceptable (< 100ms target)

### ✓ Security

- [ ] No hardcoded secrets (passwords, tokens, keys)
- [ ] Environment variables used for sensitive configuration
- [ ] No sensitive data in logs
- [ ] SQL injection prevented (parameterized queries)
- [ ] Input validation performed
- [ ] OWASP top 10 security issues addressed

### ✓ Architecture

- [ ] Code respects Clean Architecture layers
- [ ] Dependencies point inward toward domain
- [ ] No circular dependencies
- [ ] Business logic in domain layer
- [ ] Data access in repository layer
- [ ] UI isolated from domain logic
- [ ] Infrastructure abstracted behind interfaces
- [ ] SOLID principles followed
- [ ] Design patterns applied appropriately

### ✓ Financial Rules

- [ ] No financial calculations in UI layer
- [ ] No financial calculations in JavaScript
- [ ] No business logic in repository layer
- [ ] Decimal used for all monetary values (never float)
- [ ] All calculations are reproducible
- [ ] Every financial formula includes references
- [ ] Nominal vs Market values properly separated
- [ ] Accounting vs Fair values properly separated

### ✓ Code Review

- [ ] Code reviewed by at least one other developer
- [ ] All review comments addressed
- [ ] Reviewer approved changes
- [ ] No merge conflicts
- [ ] Branch up-to-date with main

### ✓ No Technical Debt

- [ ] No TODO comments left in code
- [ ] No FIXME comments left in code
- [ ] No pass statements in production code
- [ ] No dead code or unused imports
- [ ] No placeholder implementations
- [ ] No commented-out code

### ✓ Continuous Integration

- [ ] All CI checks pass
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)
- [ ] Tests pass (pytest)
- [ ] Coverage meets minimum (90%)
- [ ] Documentation builds successfully
- [ ] No security vulnerabilities detected

---

## Summary

These standards are **mandatory for every future module generated for AIP Enterprise**.

Code quality, testability, and maintainability are non-negotiable requirements. Every module must follow these standards without exception.

**Remember:** Code quality is always more important than implementation speed.

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-27  
**Approved By:** AIP Enterprise Architecture Team  
**Status:** MANDATORY - Effective Immediately
