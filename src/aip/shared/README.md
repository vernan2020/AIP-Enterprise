# AIP Shared Foundation

Shared Foundation provides reusable, production-ready building blocks for AIP Enterprise domain and application layers.

## Modules

- `validation`: Guard clauses and domain validation exceptions.
- `math`: Deterministic financial math with `Decimal`, percentages, and interpolation.
- `conventions`: Financial day-count, coupon, frequency, and business-day conventions.
- `calendars`: Costa Rica business calendar and holiday provider.
- `dates`: Business date value objects and period/range utilities.
- `money`: Currency, money arithmetic, and exchange rates.
- `serialization`: JSON serializers for `Decimal`, `date`, and `datetime`.
- `collections`: Immutable list, dict, and set wrappers.

## Costa Rica Holiday Policy

- The default Costa Rica statutory holiday provider includes national statutory holidays only.
- August 2 (Our Lady of Los Angeles / Patrona) is not treated as a universal national banking holiday by default.
- Institutions that observe August 2 can enable it explicitly through institutional holiday configuration by year.

## Design Principles

- Immutability first: value objects are frozen and hashable.
- Decimal safety: financial calculations avoid float precision errors.
- Explicit validation: fail fast with typed validation exceptions.
- Domain-oriented APIs: types and methods model financial language directly.

## Quick Examples

```python
from decimal import Decimal
from datetime import date

from src.aip.shared.money import Money, Currency
from src.aip.shared.serialization import JsonSerializer
from src.aip.shared.calendars import CostaRicaCalendar
from src.aip.shared.dates import BusinessDate

amount = Money(Decimal("1000.00"), Currency.USD)
trade_date = BusinessDate(date(2026, 7, 27), CostaRicaCalendar())
next_day = trade_date.next_business_day()

payload = {
    "amount": amount.amount,
    "currency": str(amount.currency),
    "trade_date": trade_date.date,
    "next_business_day": next_day.date,
}

json_payload = JsonSerializer.serialize(payload)
```

## Error Handling

Validation helpers raise specific exceptions from `src.aip.shared.validation.exceptions`, including:

- `RequiredValueError`
- `PositiveValueError`
- `NotEmptyError`
- `RangeError`
- `InvalidFormatError`

Use these exceptions to return precise diagnostics in application services.

## Testing

Unit tests are located under:

- `tests/unit/shared/validation`
- `tests/unit/shared/math`
- `tests/unit/shared/calendars`
- `tests/unit/shared/dates`
- `tests/unit/shared/money`
- `tests/unit/shared/serialization`
- `tests/unit/shared/collections`

Current baseline for shared foundation tests:

- `257 passed`
- `97%` coverage for `src/aip/shared`
