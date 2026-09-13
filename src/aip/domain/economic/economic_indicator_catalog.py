from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EconomicIndicatorCategory(str, Enum):
    ACTIVITY = "ACTIVITY"
    PRICES = "PRICES"
    INTEREST_RATES = "INTEREST_RATES"
    FX = "FX"
    LABOR = "LABOR"


class EconomicIndicatorFrequency(str, Enum):
    DAILY = "DAILY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"


@dataclass(frozen=True, slots=True)
class EconomicIndicatorDefinition:
    code: str
    name: str
    category: EconomicIndicatorCategory
    frequency: EconomicIndicatorFrequency
    unit: str
    source: str
    currency: str | None = None
    tenor: str | None = None
    derived: bool = False


def _build_tri_definitions(
    *,
    currency: str,
) -> tuple[EconomicIndicatorDefinition, ...]:
    tenors = (
        ("1W", "1 semana"),
        ("1M", "1 mes"),
        ("3M", "3 meses"),
        ("6M", "6 meses"),
        ("9M", "9 meses"),
        ("12M", "12 meses"),
        ("24M", "24 meses"),
        ("36M", "36 meses"),
        ("60M", "60 meses"),
    )

    return tuple(
        EconomicIndicatorDefinition(
            code=f"TRI_{currency}_{tenor_code}",
            name=("Tasa de Referencia Interbancaria " f"{currency} - {tenor_name}"),
            category=EconomicIndicatorCategory.INTEREST_RATES,
            frequency=EconomicIndicatorFrequency.DAILY,
            unit="%",
            source="BCCR",
            currency=currency,
            tenor=tenor_code,
        )
        for tenor_code, tenor_name in tenors
    )


TRI_CRC_DEFINITIONS = _build_tri_definitions(currency="CRC")
TRI_USD_DEFINITIONS = _build_tri_definitions(currency="USD")


ECONOMIC_INDICATOR_CATALOG: tuple[EconomicIndicatorDefinition, ...] = (
    EconomicIndicatorDefinition(
        code="TPM",
        name="Tasa de Política Monetaria",
        category=EconomicIndicatorCategory.INTEREST_RATES,
        frequency=EconomicIndicatorFrequency.DAILY,
        unit="%",
        source="BCCR",
        currency="CRC",
    ),
    EconomicIndicatorDefinition(
        code="TBP",
        name="Tasa Básica Pasiva",
        category=EconomicIndicatorCategory.INTEREST_RATES,
        frequency=EconomicIndicatorFrequency.DAILY,
        unit="%",
        source="BCCR",
        currency="CRC",
    ),
    *TRI_CRC_DEFINITIONS,
    *TRI_USD_DEFINITIONS,
    EconomicIndicatorDefinition(
        code="FX",
        name="Tipo de Cambio",
        category=EconomicIndicatorCategory.FX,
        frequency=EconomicIndicatorFrequency.DAILY,
        unit="CRC/USD",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="FX_BUY",
        name="Tipo de Cambio Compra",
        category=EconomicIndicatorCategory.FX,
        frequency=EconomicIndicatorFrequency.DAILY,
        unit="CRC/USD",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="FX_SELL",
        name="Tipo de Cambio Venta",
        category=EconomicIndicatorCategory.FX,
        frequency=EconomicIndicatorFrequency.DAILY,
        unit="CRC/USD",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="INFLATION",
        name="Inflación Interanual",
        category=EconomicIndicatorCategory.PRICES,
        frequency=EconomicIndicatorFrequency.MONTHLY,
        unit="%",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="IMAE",
        name="IMAE Tendencia-Ciclo",
        category=EconomicIndicatorCategory.ACTIVITY,
        frequency=EconomicIndicatorFrequency.MONTHLY,
        unit="%",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="GDP",
        name="Producto Interno Bruto Real",
        category=EconomicIndicatorCategory.ACTIVITY,
        frequency=EconomicIndicatorFrequency.QUARTERLY,
        unit="%",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="LABOR_FORCE",
        name="Fuerza de Trabajo",
        category=EconomicIndicatorCategory.LABOR,
        frequency=EconomicIndicatorFrequency.QUARTERLY,
        unit="Personas",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="EMPLOYED",
        name="Población Ocupada",
        category=EconomicIndicatorCategory.LABOR,
        frequency=EconomicIndicatorFrequency.QUARTERLY,
        unit="Personas",
        source="BCCR",
    ),
    EconomicIndicatorDefinition(
        code="UNEMPLOYMENT",
        name="Tasa de Desempleo",
        category=EconomicIndicatorCategory.LABOR,
        frequency=EconomicIndicatorFrequency.QUARTERLY,
        unit="%",
        source="BCCR",
        derived=True,
    ),
)


def get_indicator_definition(code: str) -> EconomicIndicatorDefinition | None:
    normalized = code.strip().upper()
    for indicator in ECONOMIC_INDICATOR_CATALOG:
        if indicator.code == normalized:
            return indicator
    return None


def get_tri_definitions(currency: str) -> tuple[EconomicIndicatorDefinition, ...]:
    normalized_currency = currency.strip().upper()
    if normalized_currency not in {"CRC", "USD"}:
        return ()
    return tuple(
        indicator
        for indicator in ECONOMIC_INDICATOR_CATALOG
        if indicator.code.startswith(f"TRI_{normalized_currency}_")
    )
