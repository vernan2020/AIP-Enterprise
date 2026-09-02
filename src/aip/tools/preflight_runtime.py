from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def _exists(path: str | None) -> bool:
    return bool(path and Path(path).exists())


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate AIP configured runtime readiness")
    parser.add_argument(
        "--deep",
        action="store_true",
        default=_env_flag("AIP_DEEP_PREFLIGHT"),
        help="Materialize configured providers and require institutional data before returning READY.",
    )
    return parser


def _validate_payload(
    label: str,
    payload: Any,
    failures: list[str],
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        failures.append(f"{label} provider returned a non-dict payload")
        return None
    return payload


def _run_deep_checks(
    *,
    config: Any,
    sources: Any,
    failures: list[str],
) -> None:
    """Exercise the institutional composition without duplicating UI wiring."""
    from aip.product.configured.protocols import (
        EconomicIndicatorsProvider,
        LiquidityDataProvider,
        MarketDataProvider,
        PortfolioDataProvider,
    )
    from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap

    try:
        factory, _steps = DemoBootstrap(
            config,
            source_config=sources,
        ).bootstrap(correlation_id="configured-deep-preflight")
    except Exception as exc:
        failures.append(f"configured composition failed: {type(exc).__name__}: {exc}")
        return

    container = factory.container

    try:
        portfolio = _validate_payload(
            "portfolio",
            container.resolve(PortfolioDataProvider).get_portfolio(),
            failures,
        )
        if portfolio is not None:
            positions = portfolio.get("positions")
            if not isinstance(positions, list) or not positions:
                failures.append("portfolio provider returned no positions")
            valuation_date = portfolio.get("valuation_date")
            if valuation_date is None:
                failures.append("portfolio provider returned no valuation_date")
            print(
                "Deep portfolio: "
                f"{len(positions) if isinstance(positions, list) else 0} positions; "
                f"valuation_date={valuation_date}"
            )
    except Exception as exc:
        failures.append(f"portfolio materialization failed: {type(exc).__name__}: {exc}")

    try:
        market = _validate_payload(
            "market",
            container.resolve(MarketDataProvider).get_market(),
            failures,
        )
        if market is not None:
            print(f"Deep market: keys={len(market)}")
    except Exception as exc:
        failures.append(f"market materialization failed: {type(exc).__name__}: {exc}")

    try:
        liquidity = _validate_payload(
            "liquidity",
            container.resolve(LiquidityDataProvider).get_liquidity(),
            failures,
        )
        if liquidity is not None:
            print(f"Deep liquidity: keys={len(liquidity)}")
    except Exception as exc:
        failures.append(f"liquidity materialization failed: {type(exc).__name__}: {exc}")

    try:
        economic = _validate_payload(
            "economic",
            container.resolve(EconomicIndicatorsProvider).get_indicators(),
            failures,
        )
        if economic is not None:
            indicators = economic.get("indicators")
            if not isinstance(indicators, list) or not indicators:
                failures.append("economic provider returned no indicators")
            status = economic.get("status")
            if status != "AVAILABLE":
                failures.append(f"economic provider status is {status!r}, expected 'AVAILABLE'")
            print(
                "Deep macro: "
                f"{len(indicators) if isinstance(indicators, list) else 0} indicators; "
                f"source={economic.get('source')}; status={status}"
            )
    except Exception as exc:
        failures.append(f"economic materialization failed: {type(exc).__name__}: {exc}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    loader = EnvironmentLoader()
    config = loader.load()
    sources = loader.load_source_config()

    print("AIP CONFIGURED PREFLIGHT")
    print(f"Mode: {'DEEP' if args.deep else 'FAST'}")
    print(f"Execution mode: {config.execution_mode}")
    print(f"Cutoff: {config.data_cutoff_date}")
    print(f"Portfolio root: {sources.folder_watch.portfolio_root}")
    print(f"ICL root: {sources.folder_watch.icl_root}")
    print(f"Vector path: {sources.vector.path}")
    print(f"BCCR base URL: {sources.bccr.base_url}")
    print(f"BCCR credentials: {'SET' if sources.bccr.token else 'LOCAL-HISTORY FALLBACK'}")

    failures: list[str] = []
    if config.execution_mode != "CONFIGURED":
        failures.append("execution mode is not CONFIGURED")
    if not _exists(sources.folder_watch.portfolio_root):
        failures.append("portfolio root is unavailable")
    if not _exists(sources.folder_watch.icl_root):
        failures.append("ICL root is unavailable")
    if not _exists(sources.vector.path):
        failures.append("vector path is unavailable")

    critical_modules = [
        Path("src/aip/product/configured/services/configured_portfolio_var_service.py"),
        Path("src/aip/product/configured/adapters/configured_market_provider.py"),
        Path("src/aip/product/configured/adapters/configured_liquidity_provider.py"),
        Path("src/aip/product/configured/adapters/configured_economic_indicators_provider.py"),
        Path("src/aip/ui/modules/macro_intelligence/views/macro_intelligence_view.py"),
        Path("src/aip/product/economic/economic_snapshot_store.py"),
    ]
    for module in critical_modules:
        if not module.exists():
            failures.append(f"critical runtime module missing: {module}")

    if args.deep and not failures:
        _run_deep_checks(
            config=config,
            sources=sources,
            failures=failures,
        )

    if failures:
        print("Status: FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("Status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
