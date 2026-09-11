from __future__ import annotations

from aip.product.configured.services.institutional_portfolio_rotation_service import (
    InstitutionalPortfolioRotationService,
)


def _source(**overrides):
    payload = {
        "series": "SRC-1",
        "issuer": "G",
        "currency": "CRC",
        "curve_id": "GOBIERNO_CRC",
        "spread_bp": -15.0,
        "market_yield": 5.00,
        "curve_yield": 5.15,
        "tenor": 3.0,
        "market_value_crc": 1_000_000.0,
        "classification": "RICH",
    }
    payload.update(overrides)
    return payload


def _target(**overrides):
    payload = {
        "series": "TGT-1",
        "issuer": "G",
        "curve_id": "GOBIERNO_CRC",
        "spread_bp": 20.0,
        "market_yield": 5.35,
        "curve_yield": 5.15,
        "tenor": 3.2,
        "market_price": 99.5,
        "in_portfolio": False,
        "classification": "BARATO",
    }
    payload.update(overrides)
    return payload


def test_rotation_screening_builds_same_curve_candidate() -> None:
    service = InstitutionalPortfolioRotationService()

    results = service.calculate([_source()], [_target()])

    assert len(results) == 1
    result = results[0]
    assert result.source_series == "SRC-1"
    assert result.target_series == "TGT-1"
    assert result.spread_improvement_bp == 35.0
    assert round(result.yield_improvement_bp, 8) == 35.0
    assert result.screening_status == "CANDIDATO"
    assert result.signal_type == "RELATIVE_VALUE_ROTATION"
    assert result.requires_duration_review is True
    assert result.requires_liquidity_review is True
    assert result.requires_concentration_review is True


def test_rotation_screening_never_crosses_curve_or_same_security() -> None:
    service = InstitutionalPortfolioRotationService()

    results = service.calculate(
        [_source()],
        [
            _target(series="SRC-1"),
            _target(series="USD-1", curve_id="GOBIERNO_USD"),
        ],
    )

    assert results == ()


def test_existing_target_requires_review_instead_of_candidate() -> None:
    service = InstitutionalPortfolioRotationService()

    results = service.calculate([_source()], [_target(in_portfolio=True)])

    assert len(results) == 1
    assert results[0].screening_status == "REVISAR"


def test_service_ignores_non_rich_sources_and_non_cheap_targets() -> None:
    service = InstitutionalPortfolioRotationService()

    assert service.calculate([_source(classification="NEUTRAL")], [_target()]) == ()
    assert service.calculate([_source()], [_target(classification="NEUTRAL")]) == ()


def test_service_ignores_malformed_rows_without_failing_workspace() -> None:
    service = InstitutionalPortfolioRotationService()

    results = service.calculate(
        [_source(), {"classification": "RICH"}],
        [_target(), {"classification": "BARATO", "series": "BROKEN"}],
    )

    assert len(results) == 1
