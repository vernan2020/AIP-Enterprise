"""Financial mathematics domain package."""

from aip.domain.financial_math.bond_metrics.accrued_interest import accrued_interest
from aip.domain.financial_math.bond_metrics.clean_dirty_price import clean_price, dirty_price
from aip.domain.financial_math.bond_metrics.convexity import convexity
from aip.domain.financial_math.bond_metrics.dv01 import dv01
from aip.domain.financial_math.bond_metrics.effective_duration import effective_duration
from aip.domain.financial_math.bond_metrics.macaulay_duration import macaulay_duration
from aip.domain.financial_math.bond_metrics.modified_duration import modified_duration
from aip.domain.financial_math.bond_metrics.pvbp import pvbp
from aip.domain.financial_math.cashflows.cashflow import CashFlow
from aip.domain.financial_math.cashflows.cashflow_series import CashFlowSeries
from aip.domain.financial_math.curves.bootstrap import BootstrapResult, bootstrap_zero_curve
from aip.domain.financial_math.curves.curve_point import CurvePoint
from aip.domain.financial_math.curves.nelson_siegel import (
    nelson_siegel_curve,
    nelson_siegel_zero_rate,
)
from aip.domain.financial_math.curves.svensson import svensson_curve, svensson_zero_rate
from aip.domain.financial_math.curves.yield_curve import YieldCurve
from aip.domain.financial_math.discounting.compounding import (
    accumulation_factor,
    discount_factor,
    equivalent_rate,
)
from aip.domain.financial_math.discounting.future_value import future_value, future_value_series
from aip.domain.financial_math.discounting.present_value import present_value, present_value_series
from aip.domain.financial_math.exceptions import (
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
from aip.domain.financial_math.interpolation.linear import interpolate_linear
from aip.domain.financial_math.interpolation.logarithmic import interpolate_logarithmic
from aip.domain.financial_math.rates.effective_rate import EffectiveRate
from aip.domain.financial_math.rates.forward_rate import ForwardRate
from aip.domain.financial_math.rates.interest_rate import InterestRate
from aip.domain.financial_math.rates.nominal_rate import NominalRate
from aip.domain.financial_math.rates.zero_rate import ZeroRate
from aip.domain.financial_math.root_finding.bisection import bisection_solve
from aip.domain.financial_math.root_finding.brent import brent_solve
from aip.domain.financial_math.root_finding.newton_raphson import newton_raphson_solve
from aip.domain.financial_math.yield_calculations.internal_rate_of_return import (
    internal_rate_of_return,
    money_weighted_return,
)
from aip.domain.financial_math.yield_calculations.yield_to_maturity import yield_to_maturity

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
