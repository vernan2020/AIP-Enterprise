from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from aip.product.configured.services.institutional_market_curve_service import (
    InstitutionalMarketCurveService,
)


def _records(
    *,
    issuer: str,
    mnemonic: str,
    prefix: str,
    cutoff: date,
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for index, years in enumerate((1, 2, 4, 7, 10, 15), start=1):
        maturity = cutoff + timedelta(days=round(years * 365.25))
        observations.append(
            {
                "issuer": issuer,
                "instrument_type_or_mnemonic": mnemonic,
                "series_or_security_code": f"{prefix}{index}",
                "isin_if_present": f"CR{prefix}{index:08d}",
                "maturity_date_if_present": maturity,
                "market_yield": Decimal("3.50") + Decimal(str(years)) * Decimal("0.08"),
            }
        )
    return observations


def test_builds_three_institutional_curves_from_eligible_pipca_records() -> None:
    cutoff = date(2026, 8, 27)
    records = [
        *_records(issuer="G", mnemonic="tp", prefix="GCRC", cutoff=cutoff),
        *_records(issuer="G", mnemonic="tp$", prefix="GUSD", cutoff=cutoff),
        *_records(issuer="BCCR", mnemonic="bem", prefix="BCCR", cutoff=cutoff),
    ]

    results = InstitutionalMarketCurveService().build_curves(records, cutoff)

    assert [result.curve_id for result in results] == [
        "GOBIERNO_CRC",
        "GOBIERNO_USD",
        "BCCR_CRC",
    ]
    assert all(result.observation_count == 6 for result in results)
    assert all(result.min_tenor > 0 for result in results)
    assert all(result.max_tenor > result.min_tenor for result in results)
    assert all(result.nelson_siegel.tau > 0 for result in results)
    assert all(result.nelson_siegel.metrics.rmse >= 0 for result in results)
    assert all(result.polynomial_degree2.metrics.rmse >= 0 for result in results)


def test_does_not_fabricate_curve_with_insufficient_observations() -> None:
    cutoff = date(2026, 8, 27)
    records = [
        {
            "issuer": "BCCR",
            "instrument_type_or_mnemonic": "bem",
            "series_or_security_code": "ONLY1",
            "maturity_date_if_present": cutoff + timedelta(days=365),
            "market_yield": Decimal("3.25"),
        }
    ]

    results = InstitutionalMarketCurveService().build_curves(records, cutoff)

    assert results == ()


def test_ignores_expired_invalid_and_duplicate_market_observations() -> None:
    cutoff = date(2026, 8, 27)
    records = _records(issuer="G", mnemonic="tp", prefix="GCRC", cutoff=cutoff)
    records.append(dict(records[0]))
    records.extend(
        [
            {
                "issuer": "G",
                "instrument_type_or_mnemonic": "tp",
                "series_or_security_code": "EXPIRED",
                "maturity_date_if_present": cutoff - timedelta(days=1),
                "market_yield": Decimal("4.00"),
            },
            {
                "issuer": "G",
                "instrument_type_or_mnemonic": "tp",
                "series_or_security_code": "NOYIELD",
                "maturity_date_if_present": cutoff + timedelta(days=365),
                "market_yield": None,
            },
        ]
    )

    results = InstitutionalMarketCurveService().build_curves(records, cutoff)

    assert len(results) == 1
    assert results[0].curve_id == "GOBIERNO_CRC"
    assert results[0].observation_count == 6
