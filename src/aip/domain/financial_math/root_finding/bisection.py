from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from aip.domain.financial_math.exceptions import ConvergenceError, InvalidBracketError


@dataclass(frozen=True, slots=True)
class ConvergenceResult:
    root: Decimal
    iterations: int
    converged: bool
    residual: Decimal
    method: str


def bisection_solve(
    function: Callable[[Decimal], Decimal],
    lower: Decimal,
    upper: Decimal,
    *,
    tolerance: Decimal = Decimal("1e-10"),
    max_iterations: int = 100,
) -> ConvergenceResult:
    if lower >= upper:
        raise InvalidBracketError("Lower bound must be strictly less than upper bound")
    f_lower = function(lower)
    f_upper = function(upper)
    if f_lower == 0:
        return ConvergenceResult(
            root=lower, iterations=0, converged=True, residual=Decimal("0"), method="bisection"
        )
    if f_upper == 0:
        return ConvergenceResult(
            root=upper, iterations=0, converged=True, residual=Decimal("0"), method="bisection"
        )
    if f_lower * f_upper > 0:
        raise InvalidBracketError("Function values must have opposite signs at the bracket ends")
    for iteration in range(1, max_iterations + 1):
        midpoint = (lower + upper) / Decimal("2")
        f_midpoint = function(midpoint)
        if abs(f_midpoint) <= tolerance:
            return ConvergenceResult(
                root=midpoint,
                iterations=iteration,
                converged=True,
                residual=abs(f_midpoint),
                method="bisection",
            )
        if f_lower * f_midpoint <= 0:
            upper = midpoint
            f_upper = f_midpoint
        else:
            lower = midpoint
            f_lower = f_midpoint
    raise ConvergenceError("Bisection did not converge")
