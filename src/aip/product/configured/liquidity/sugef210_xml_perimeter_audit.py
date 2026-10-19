"""Read-only SUGEF 2-10 coverage of credit, deposits and borrowings XML.

Balances and the presence of dates are NOT dated payment amounts. This audit
preserves original currency and account codes, never infers runoff, interest,
amortization or sight-deposit withdrawal, and makes no cashflow bookings.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader


@dataclass(frozen=True, slots=True)
class XMLLiquiditySourceLayout:
    key: str
    balance_field: str
    currency_field: str
    accounting_field: str
    date_fields: tuple[str, ...]
    classification_field: str = ""


_LAYOUTS = (
    XMLLiquiditySourceLayout(
        "CREDIT",
        "SaldoPrincipalOperacionCrediticia",
        "TipoMonedaOperacion",
        "CuentaContablePrincipal",
        ("FechaVencimiento", "FechaProximoPagoPrincipal", "FechaProximoPagoIntereses"),
    ),
    XMLLiquiditySourceLayout(
        "CAPTACIONES",
        "SaldoPrincipal",
        "TipoMonedaObligacion",
        "CuentaContablePrincipal",
        ("FechaVencimiento",),
        "TipoCuenta",
    ),
    XMLLiquiditySourceLayout(
        "BORROWING",
        "SaldoPrincipal",
        "TipoMonedaObligacion",
        "CuentaContablePrincipal",
        ("FechaVencimiento", "FechaProximoPagoPrincipal", "FechaProximoPagoInteres"),
    ),
    XMLLiquiditySourceLayout(
        "BORROWING_MATURITY",
        "SaldoaPagarPrincipal",
        "TipoMonedaObligacion",
        "CuentaContablePrincipal",
        (),
        "TipoRangoPasivo",
    ),
)


@dataclass(frozen=True, slots=True)
class XMLLiquiditySourceCoverage:
    key: str
    cutoff: date
    status: str
    file_name: str | None
    source_sha256: str | None
    reporting_period: date | None
    records: int
    missing_balance: int
    invalid_balance: int
    missing_currency: int
    missing_account: int
    date_counts: tuple[tuple[str, int, int, int], ...]
    native_balances: tuple[tuple[str, Decimal], ...]
    original_categories: tuple[tuple[str, int], ...]
    error_type: str | None = None

    @property
    def payment_amounts_certified(self) -> bool:
        """Neither maturity dates nor balances prove individual settlement amounts."""
        return False


def _native_balance(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def _source_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%d/%m/%Y")
    except ValueError:
        return False
    return True


def audit_xml_liquidity_perimeters(
    *, reader: XMLConfiaMonthlySourceReader, cutoff: date
) -> tuple[XMLLiquiditySourceCoverage, ...]:
    """Inspect each real configured XML independently; partial failures stay visible."""
    output: list[XMLLiquiditySourceCoverage] = []
    for layout in _LAYOUTS:
        try:
            source = reader.resolve_source(key=layout.key, cutoff_date=cutoff)
        except (OSError, ValueError, KeyError) as exc:
            output.append(
                XMLLiquiditySourceCoverage(
                    key=layout.key,
                    cutoff=cutoff,
                    status="SOURCE_UNAVAILABLE_NOT_ASSUMED_ZERO",
                    file_name=None,
                    source_sha256=None,
                    reporting_period=None,
                    records=0,
                    missing_balance=0,
                    invalid_balance=0,
                    missing_currency=0,
                    missing_account=0,
                    date_counts=(),
                    native_balances=(),
                    original_categories=(),
                    error_type=type(exc).__name__,
                )
            )
            continue

        rows = 0
        missing_balance = 0
        invalid_balance = 0
        missing_currency = 0
        missing_account = 0
        native_balances: dict[str, Decimal] = defaultdict(Decimal)
        categories: Counter[str] = Counter()
        date_counts: dict[str, list[int]] = {
            name: [0, 0, 0] for name in layout.date_fields
        }  # supplied, missing, malformed
        for record in reader.iter_records(source):
            rows += 1
            values = record.values
            currency = (values.get(layout.currency_field) or "").strip()
            account = (values.get(layout.accounting_field) or "").strip()
            raw_balance = (values.get(layout.balance_field) or "").strip()
            balance = _native_balance(raw_balance)
            if not raw_balance:
                missing_balance += 1
            elif balance is None:
                invalid_balance += 1
            if not currency:
                missing_currency += 1
            if not account:
                missing_account += 1
            if balance is not None and currency:
                native_balances[currency] += balance
            if layout.classification_field:
                category = (values.get(layout.classification_field) or "").strip()
                categories[category if category else "(SIN CÓDIGO)"] += 1
            for field in layout.date_fields:
                raw_date = (values.get(field) or "").strip()
                if not raw_date:
                    date_counts[field][1] += 1
                elif _source_date(raw_date):
                    date_counts[field][0] += 1
                else:
                    date_counts[field][2] += 1
        output.append(
            XMLLiquiditySourceCoverage(
                key=layout.key,
                cutoff=cutoff,
                status="SOURCE_FIELDS_INSPECTED_NOT_A_PAYMENT_SCHEDULE",
                file_name=source.path.name,
                source_sha256=reader.sha256(source.path),
                reporting_period=source.header.periodo,
                records=rows,
                missing_balance=missing_balance,
                invalid_balance=invalid_balance,
                missing_currency=missing_currency,
                missing_account=missing_account,
                date_counts=tuple(
                    (name, counts[0], counts[1], counts[2])
                    for name, counts in sorted(date_counts.items())
                ),
                native_balances=tuple(sorted(native_balances.items())),
                original_categories=tuple(sorted(categories.items())),
            )
        )
    return tuple(output)


def summarize_xml_liquidity_perimeters(
    reports: tuple[XMLLiquiditySourceCoverage, ...],
) -> list[dict[str, object]]:
    """JSON-ready source facts without labelling balances contractual cash."""
    return [
        {
            "source_key": row.key,
            "status": row.status,
            "file": row.file_name,
            "cutoff": row.cutoff.isoformat(),
            "reporting_period": (
                row.reporting_period.isoformat() if row.reporting_period else None
            ),
            "sha256": row.source_sha256,
            "records": row.records,
            "missing_balance": row.missing_balance,
            "invalid_balance": row.invalid_balance,
            "missing_currency": row.missing_currency,
            "missing_account": row.missing_account,
            "dates": [
                {"field": name, "valid": valid, "missing": missing, "invalid": invalid}
                for name, valid, missing, invalid in row.date_counts
            ],
            "source_currency_balances_not_cashflows": {
                code: str(amount) for code, amount in row.native_balances
            },
            "raw_classification_codes": dict(row.original_categories),
            "individual_payment_amounts_certified": False,
            "error_type": row.error_type,
        }
        for row in reports
    ]
