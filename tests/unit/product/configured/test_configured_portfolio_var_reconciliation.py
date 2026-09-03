from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import MethodType
from typing import Any, cast

import pytest

from aip.product.configured.readers.pipca_vector_reader import InstitutionalVectorRecord
from aip.product.configured.repositories.pipca_historical_price_repository import (
    PiPCAHistoricalPriceRepository,
)
from aip.product.configured.services.configured_portfolio_var_service import (
    ConfiguredPortfolioVaRResult,
    ConfiguredPortfolioVaRService,
)


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ({"classification": "C.A VENCIMIENTO", "product_code": "BONO"}, "COST_AMORTIZED"),
        ({"classification": "V.R BCCR", "product_code": " icp "}, "ICP_OPERATION"),
        ({"classification": "V.R GOBIERNO", "product_code": "MIL"}, "MIL_OPERATION"),
        ({"classification": "V.R GOBIERNO", "product_code": "BONO"}, None),
    ],
)
def test_var_policy_reconciles_institutional_exclusions(
    position: dict[str, str], expected: str | None
) -> None:
    assert ConfiguredPortfolioVaRService._policy_exclusion_reason(position) == expected


def test_icp_regression_removes_exact_19_billion_exposure_difference() -> None:
    institutional_exposure = Decimal("227662012586.13223")
    positions = (
        {
            "classification": "V.R BCCR",
            "product_code": "BONO",
            "market_value_crc": institutional_exposure,
        },
        {
            "classification": "V.R BCCR",
            "product_code": "ICP",
            "market_value_crc": Decimal("19000000000"),
        },
    )

    eligible = sum(
        (
            cast(Decimal, position["market_value_crc"])
            for position in positions
            if ConfiguredPortfolioVaRService._policy_exclusion_reason(position) is None
        ),
        Decimal("0"),
    )

    assert eligible == institutional_exposure
    assert sum((cast(Decimal, row["market_value_crc"]) for row in positions), Decimal("0")) - eligible == Decimal(
        "19000000000"
    )


def test_calculate_reuses_portfolio_loaded_to_resolve_valuation_date() -> None:
    class _Provider:
        calls = 0

        def get_portfolio(self) -> dict[str, Any]:
            self.calls += 1
            return {"valuation_date": date(2026, 8, 28), "positions": []}

    provider = _Provider()
    service = ConfiguredPortfolioVaRService.__new__(ConfiguredPortfolioVaRService)
    service._portfolio_provider = provider
    service._result_cache = {}
    service._valuation_date_context = None
    service._config = cast(Any, object())
    sentinel = cast(ConfiguredPortfolioVaRResult, object())

    def _calculate_uncached(
        _self: ConfiguredPortfolioVaRService,
        *,
        valuation_date: date | None = None,
        portfolio: dict[str, Any] | None = None,
    ) -> ConfiguredPortfolioVaRResult:
        assert valuation_date == date(2026, 8, 28)
        assert portfolio == {"valuation_date": date(2026, 8, 28), "positions": []}
        return sentinel

    service._calculate_uncached = MethodType(_calculate_uncached, service)  # type: ignore[method-assign]

    assert service.calculate() is sentinel
    assert provider.calls == 1


def _record(*, series: str, normalized_series: str) -> InstitutionalVectorRecord:
    return InstitutionalVectorRecord(
        issuer="G",
        instrument_type_or_mnemonic="BONO",
        series_or_security_code=series,
        normalized_issuer_key="g",
        normalized_series_key=normalized_series,
        isin_if_present="",
        maturity_date_if_present=date(2030, 1, 1),
        coupon_or_reference_value=Decimal("5"),
        market_price=Decimal("100"),
        market_yield=Decimal("5"),
        spread_or_auxiliary_value=None,
        record_status="ACTIVE",
        source_cutoff=date(2026, 8, 28),
        source_line=1,
    )


def test_pipca_builds_one_series_index_per_vector_file(tmp_path: Path) -> None:
    repository = PiPCAHistoricalPriceRepository(tmp_path)
    path = tmp_path / "vector" / "VectorPiPCA_20260828.txt"
    first = _record(series="SERIE A", normalized_series="SERIE-A")
    second = _record(series="SERIE B", normalized_series="SERIE-B")
    repository._record_cache[path] = (first, second)

    assert repository._records_for_series(path, "seriea") == (first,)
    index = repository._records_by_series_cache[path]
    assert repository._records_for_series(path, "serieb") == (second,)
    assert repository._records_by_series_cache[path] is index
    assert set(index) == {"seriea", "serieb"}
