from __future__ import annotations

import math
from decimal import Decimal

from aip.domain.financial_math.exceptions import InvalidRateError


def svensson_zero_rate(
    tenor: Decimal,
    *,
    beta0: Decimal,
    beta1: Decimal,
    beta2: Decimal,
    beta3: Decimal,
    tau1: Decimal,
    tau2: Decimal,
) -> Decimal:
    if tau1 <= 0 or tau2 <= 0:
        raise InvalidRateError("Tau parameters must be positive")
    if tenor == 0:
        return beta0
    scaled1 = tenor / tau1
    scaled2 = tenor / tau2
    factor1 = (Decimal("1") - Decimal(str(math.exp(-float(scaled1))))) / scaled1
    factor2 = (Decimal("1") - Decimal(str(math.exp(-float(scaled2))))) / scaled2
    return (
        beta0
        + beta1 * factor1
        + beta2 * (factor1 - Decimal(str(math.exp(-float(scaled1)))))
        + beta3 * (factor2 - Decimal(str(math.exp(-float(scaled2)))))
    )


def svensson_curve(
    tenors: list[Decimal],
    *,
    beta0: Decimal,
    beta1: Decimal,
    beta2: Decimal,
    beta3: Decimal,
    tau1: Decimal,
    tau2: Decimal,
) -> list[Decimal]:
    return [
        svensson_zero_rate(
            tenor, beta0=beta0, beta1=beta1, beta2=beta2, beta3=beta3, tau1=tau1, tau2=tau2
        )
        for tenor in tenors
    ]
