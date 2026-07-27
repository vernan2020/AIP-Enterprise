# Financial Mathematics Library

This package provides deterministic domain objects and algorithms for discounting, rates, interpolation, bond metrics and yield-curve construction.

## Design decisions

- All public financial calculations use Decimal.
- Compounding conventions are explicit and documented in each public API.
- Root-finding failures raise domain-specific exceptions rather than leaking raw numeric errors.
- Bond metrics are expressed in consistent price and rate units.
