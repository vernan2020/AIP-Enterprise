"""Financial mathematics domain package."""

from .bond_metrics.accrued_interest import accrued_interest
from .bond_metrics.clean_dirty_price import clean_price, dirty_price
from .bond_metrics.convexity import convexity
from .bond_metrics.dv01 import dv01
from .bond_metrics.effective_duration import effective_duration
from .bond_metrics.macaulay_duration import macaulay_duration
from .bond_metrics.modified_duration import modified_duration
from .bond_metrics.pvbp import pvbp
from .cashflows.cashflow import CashFlow
from .cashflows.cashflow_series import CashFlowSeries
from .curves.bootstrap import BootstrapResult, bootstrap_zero_curve
from .curves.curve_point import CurvePoint
from .curves.nelson_siegel import (
    nelson_siegel_curve,
    nelson_siegel_zero_rate,
)
from .curves.svensson import svensson_curve, svensson_zero_rate
from .curves.yield_curve import YieldCurve
from .discounting.compounding import (
    accumulation_factor,
    discount_factor,
    equivalent_rate,
)
from .discounting.future_value import future_value, future_value_series
from .discounting.present_value import present_value, present_value_series
from .exceptions import (
    BootstrapError,
    ConvergenceError,
    CurrencyMismatchError,
    CurveConstructionError,
    FinancialMathError,
    InterpolationError,
    InvalidBracketError,
    InvalidCashFlowError,
    InvalidRateError,
)
from .interpolation.linear import interpolate_linear
from .interpolation.logarithmic import interpolate_logarithmic
from .rates.effective_rate import EffectiveRate
from .rates.forward_rate import ForwardRate
from .rates.interest_rate import InterestRate
from .rates.nominal_rate import NominalRate
from .rates.zero_rate import ZeroRate
from .root_finding.bisection import bisection_solve
from .root_finding.brent import brent_solve
from .root_finding.newton_raphson import newton_raphson_solve
from .yield_calculations.internal_rate_of_return import (
    internal_rate_of_return,
    money_weighted_return,
)
from .yield_calculations.yield_to_maturity import yield_to_maturity

accrue_interest = accrued_interest

__all__ = [
    "CashFlow",
    "CashFlowSeries",
    "InterestRate",
    "EffectiveRate",
    "NominalRate",
    "ZeroRate",
    "ForwardRate",
    "CurvePoint",
    "YieldCurve",
    "BootstrapResult",
    "accumulation_factor",
    "discount_factor",
    "equivalent_rate",
    "present_value",
    "present_value_series",
    "future_value",
    "future_value_series",
    "yield_to_maturity",
    "internal_rate_of_return",
    "money_weighted_return",
    "bisection_solve",
    "newton_raphson_solve",
    "brent_solve",
    "interpolate_linear",
    "interpolate_logarithmic",
    "accrued_interest",
    "dirty_price",
    "clean_price",
    "macaulay_duration",
    "modified_duration",
    "effective_duration",
    "convexity",
    "dv01",
    "pvbp",
    "bootstrap_zero_curve",
    "nelson_siegel_zero_rate",
    "nelson_siegel_curve",
    "svensson_zero_rate",
    "svensson_curve",
    "FinancialMathError",
    "InvalidRateError",
    "InvalidCashFlowError",
    "CurrencyMismatchError",
    "ConvergenceError",
    "InvalidBracketError",
    "CurveConstructionError",
    "InterpolationError",
    "BootstrapError",
]
