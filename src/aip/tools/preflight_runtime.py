from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from aip.product.demo.configuration.environment_loader import EnvironmentLoader

_REQUIRED_MACRO_CODES = {
    "FX_SELL",
    "TPM",
    "TBP",
    "INFLATION",
    "IMAE",
    "GDP",
    "UNEMPLOYMENT",
    "TRI_CRC_12M",
    "TRI_USD_12M",
}


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
            if float(portfolio.get("market_value") or 0.0) <= 0.0:
                failures.append("portfolio provider returned non-positive market value")
            print(
                "Deep portfolio: "
                f"{len(positions) if isinstance(positions, list) else 0} positions; "
                f"valuation_date={valuation_date}; "
                f"market_value={portfolio.get('market_value')}"
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
            curves = market.get("curves")
            curve_count = len(curves) if isinstance(curves, list) else 0
            if market.get("market_status") != "Configured":
                failures.append(
                    f"market provider status is {market.get('market_status')!r}, expected 'Configured'"
                )
            if curve_count != 3:
                failures.append(f"market provider built {curve_count} curves; expected 3")
            print(
                "Deep market: "
                f"status={market.get('market_status')}; "
                f"curves={curve_count}; "
                f"RV={market.get('market_relative_value_count')}"
            )
    except Exception as exc:
        failures.append(f"market materialization failed: {type(exc).__name__}: {exc}")

    try:
        liquidity = _validate_payload(
            "liquidity",
            container.resolve(LiquidityDataProvider).get_liquidity(),
            failures,
        )
        if liquidity is not None:
            icl_source_file = liquidity.get("icl_source_file")
            icl_source_date = liquidity.get("icl_source_date")
            if not icl_source_file:
                failures.append("liquidity provider did not load an institutional ICL source file")
            if not icl_source_date:
                failures.append("liquidity provider did not return an ICL source date")
            if float(liquidity.get("hqla_capacity") or 0.0) <= 0.0:
                failures.append("liquidity provider returned non-positive HQLA capacity")
            if float(liquidity.get("mil_eligible_capacity") or 0.0) <= 0.0:
                failures.append("liquidity provider returned non-positive MIL capacity")
            print(
                "Deep liquidity: "
                f"ICL={liquidity.get('icl_total')}; "
                f"HQLA={liquidity.get('hqla_capacity')}; "
                f"MIL={liquidity.get('mil_eligible_capacity')}; "
                f"source_date={icl_source_date}; "
                f"source_file={icl_source_file}"
            )
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
                indicator_codes: set[str] = set()
            else:
                indicator_codes = {
                    str(item.get("code"))
                    for item in indicators
                    if isinstance(item, dict) and item.get("code")
                }
            status = economic.get("status")
            if status != "AVAILABLE":
                failures.append(f"economic provider status is {status!r}, expected 'AVAILABLE'")
            missing_macro = sorted(_REQUIRED_MACRO_CODES - indicator_codes)
            if missing_macro:
                failures.append(
                    "economic provider is missing required macro drivers: "
                    + ", ".join(missing_macro)
                )
            print(
                "Deep macro: "
                f"{len(indicator_codes)} indicators; "
                f"source={economic.get('source')}; status={status}; "
                f"required_missing={missing_macro or 'none'}"
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
