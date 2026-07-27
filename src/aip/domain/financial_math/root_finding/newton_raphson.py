from __future__ import annotations

from decimal import Decimal
from typing import Callable

from aip.domain.financial_math.exceptions import ConvergenceError
from aip.domain.financial_math.root_finding.bisection import ConvergenceResult


def newton_raphson_solve(
    function: Callable[[Decimal], Decimal],
    derivative: Callable[[Decimal], Decimal],
    initial_guess: Decimal,
    *,
    tolerance: Decimal = Decimal("1e-10"),
    max_iterations: int = 50,
) -> ConvergenceResult:
    value = function(initial_guess)
    if abs(value) <= tolerance:
        return ConvergenceResult(root=initial_guess, iterations=0, converged=True, residual=abs(value), method="newton")
    for iteration in range(1, max_iterations + 1):
        derivative_value = derivative(initial_guess)
        if derivative_value == 0:
            raise ConvergenceError("Derivative is zero")
        next_guess = initial_guess - value / derivative_value
        next_value = function(next_guess)
        if abs(next_value) <= tolerance:
            return ConvergenceResult(root=next_guess, iterations=iteration, converged=True, residual=abs(next_value), method="newton")
        initial_guess = next_guess
        value = next_value
    raise ConvergenceError("Newton-Raphson did not converge")
