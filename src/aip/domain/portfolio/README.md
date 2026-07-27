# Portfolio Domain

Portfolio bounded context for AIP Enterprise treasury and investments.

## Scope

- Aggregate root: Portfolio
- Entities: Position, Transaction
- Value Objects: identifiers, instrument data, valuations, risk metrics, settlement date
- Domain service: reproducible valuation and weighted analytics
- Domain events: lifecycle and mutation events

## Business Rules

- Closed portfolios reject new positions and transactions.
- Duplicate positions by business key (ISIN, settlement date, currency) are rejected.
- Transactions are immutable and validated for sign consistency.
- Net transaction amount is reproducible as gross - fees - taxes.
- Financial amounts use Decimal through shared Money and Percentage types.

## Calculation Rules

- Portfolio totals aggregate in base currency only.
- Weighted metrics use market value as weight base.
- Currency exposure is calculated as market-value totals per currency.

## Notes

- Repository abstraction is domain-only; persistence implementations are out of scope.
- Events are immutable and include id, timestamp, aggregate id, type and payload.
