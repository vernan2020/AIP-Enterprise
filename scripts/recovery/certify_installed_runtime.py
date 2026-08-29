from __future__ import annotations

import importlib
import inspect
import numbers
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _positive_numbers_for_keys(payload: Any, predicate: Callable[[str], bool]) -> list[float]:
    values: list[float] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).lower()
            if predicate(normalized) and isinstance(value, numbers.Real) and not isinstance(value, bool):
                values.append(float(value))
            values.extend(_positive_numbers_for_keys(value, predicate))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            values.extend(_positive_numbers_for_keys(item, predicate))
    return [value for value in values if value > 0.0]


def _first_existing_number(payload: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, numbers.Real) and not isinstance(value, bool):
            return float(value)
    return None


def _call_if_zero_arg(instance: Any, candidates: tuple[str, ...]) -> tuple[str | None, Any]:
    for name in candidates:
        method = getattr(instance, name, None)
        if not callable(method):
            continue
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            continue
        required = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if required:
            continue
        return name, method()
    return None, None


def _print_check(name: str, status: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def main() -> int:
    os.environ.setdefault("AIP_EXECUTION_MODE", "CONFIGURED")
    os.environ.setdefault("AIP_DEMO_MODE_ENABLED", "false")
    os.environ.setdefault("AIP_FOLDERWATCH_ENABLED", "true")
    os.environ.setdefault("AIP_VECTOR_ENABLED", "true")
    os.environ.setdefault("AIP_BCCR_ENABLED", "true")
    os.environ.setdefault("AIP_BCCR_BASE_URL", "https://apim.bccr.fi.cr")
    os.environ.setdefault("AIP_ALLOW_PRIOR_SOURCE_DATE", "true")

    failures: list[str] = []
    warnings: list[str] = []

    print("AIP ENTERPRISE - DEEP RUNTIME CERTIFICATION")
    print(f"Project root: {ROOT}")

    try:
        from aip.product.demo.configuration.environment_loader import EnvironmentLoader
        from aip.product.demo.bootstrap.demo_bootstrap import DemoBootstrap

        loader = EnvironmentLoader()
        config = loader.load()
        source_config = loader.load_source_config()
        if config.execution_mode != "CONFIGURED":
            raise RuntimeError(f"execution_mode={config.execution_mode}")
        _print_check("Configured mode", "PASS", str(config.data_cutoff_date))

        factory, startup = DemoBootstrap(config, source_config=source_config).bootstrap(
            correlation_id="certify-runtime"
        )
        failed_startup = [step for step in startup if getattr(step, "status", "") != "OK"]
        if failed_startup:
            raise RuntimeError(f"startup steps failed: {len(failed_startup)}")
        container = factory.container
        _print_check("Dependency composition", "PASS", f"startup_steps={len(startup)}")
    except Exception as exc:
        _print_check("Bootstrap/composition", "FAIL", str(exc))
        return 1

    try:
        protocols = importlib.import_module("aip.product.configured.protocols")
        portfolio_protocol = getattr(protocols, "PortfolioDataProvider")
        portfolio_provider = container.resolve(portfolio_protocol)
        portfolio = portfolio_provider.get_portfolio()
        if not isinstance(portfolio, dict):
            raise RuntimeError("portfolio provider did not return a dict")
        positions = portfolio.get("positions") or []
        market_value = _first_existing_number(
            portfolio,
            ("market_value", "market_value_crc", "total_market_value", "portfolio_market_value"),
        )
        if not isinstance(positions, list) or len(positions) <= 0:
            raise RuntimeError("portfolio has no positions")
        if market_value is None or market_value <= 0:
            raise RuntimeError("portfolio market value is unavailable or zero")
        _print_check(
            "Portfolio",
            "PASS",
            f"positions={len(positions)}, market_value={market_value:.2f}",
        )
    except Exception as exc:
        failures.append(f"Portfolio: {exc}")
        _print_check("Portfolio", "FAIL", str(exc))

    try:
        protocols = importlib.import_module("aip.product.configured.protocols")
        market_protocol = getattr(protocols, "MarketDataProvider")
        market_provider = container.resolve(market_protocol)
        market = market_provider.get_market()
        if not isinstance(market, dict) or not market:
            raise RuntimeError("market provider returned no data")
        explicit_status = str(market.get("status", market.get("data_quality_status", ""))).upper()
        if explicit_status in {"FAILED", "ERROR", "UNAVAILABLE"}:
            raise RuntimeError(f"market status={explicit_status}")
        _print_check("Market", "PASS", f"keys={len(market)}")
    except Exception as exc:
        failures.append(f"Market: {exc}")
        _print_check("Market", "FAIL", str(exc))

    try:
        protocols = importlib.import_module("aip.product.configured.protocols")
        liquidity_protocol = getattr(protocols, "LiquidityDataProvider")
        liquidity_provider = container.resolve(liquidity_protocol)
        liquidity = liquidity_provider.get_liquidity()
        if not isinstance(liquidity, dict):
            raise RuntimeError("liquidity provider did not return a dict")

        hqla_values = _positive_numbers_for_keys(
            liquidity, lambda key: "hqla" in key and ("capacity" in key or "recognized" in key or "total" in key)
        )
        mil_values = _positive_numbers_for_keys(
            liquidity, lambda key: "mil" in key and ("capacity" in key or "eligible" in key or "total" in key)
        )
        icl_values = _positive_numbers_for_keys(
            liquidity, lambda key: "icl" in key and "date" not in key and "count" not in key
        )

        if not hqla_values:
            raise RuntimeError("positive HQLA capacity was not found")
        if not mil_values:
            raise RuntimeError("positive MIL capacity was not found")
        if not icl_values:
            raise RuntimeError("positive ICL metric was not found")

        _print_check(
            "Liquidity",
            "PASS",
            f"HQLA={max(hqla_values):.4f}, MIL={max(mil_values):.4f}, ICL={max(icl_values):.4f}",
        )
    except Exception as exc:
        failures.append(f"Liquidity: {exc}")
        _print_check("Liquidity", "FAIL", str(exc))

    try:
        macro_module = importlib.import_module(
            "aip.product.configured.services.configured_macro_intelligence_service"
        )
        macro_type = getattr(macro_module, "ConfiguredMacroIntelligenceService")
        try:
            macro_service = container.resolve(macro_type)
        except Exception:
            macro_service = macro_type()
        projection = macro_service.get_projection()
        if not isinstance(projection, dict):
            raise RuntimeError("macro service did not return a dict")
        status = str(projection.get("status", "")).upper()
        rows = projection.get("rows") or []
        if status != "AVAILABLE":
            raise RuntimeError(
                projection.get("diagnostic") or f"macro projection status={status or 'N/D'}"
            )
        if not isinstance(rows, list) or len(rows) < 12:
            raise RuntimeError(f"macro projection has insufficient rows: {len(rows) if isinstance(rows, list) else 0}")
        _print_check(
            "Macro Intelligence",
            "PASS",
            f"scenario={projection.get('scenario_id')} v{projection.get('version')}, rows={len(rows)}",
        )
    except Exception as exc:
        failures.append(f"Macro Intelligence: {exc}")
        _print_check("Macro Intelligence", "FAIL", str(exc))

    try:
        var_module = importlib.import_module(
            "aip.product.configured.services.configured_portfolio_var_service"
        )
        var_type = getattr(var_module, "ConfiguredPortfolioVaRService")
        var_service = container.resolve(var_type)
        method_name, var_result = _call_if_zero_arg(
            var_service,
            ("calculate", "calculate_var", "get_var", "get_result"),
        )
        if method_name is None:
            warnings.append("VeR service resolved; no zero-argument calculation entrypoint was detected")
            _print_check("VeR service", "PASS", "resolved; calculation entrypoint requires explicit arguments")
        else:
            if var_result is None:
                raise RuntimeError(f"{method_name} returned None")
            _print_check("VeR service", "PASS", f"calculation={method_name}")
    except Exception as exc:
        failures.append(f"VeR: {exc}")
        _print_check("VeR service", "FAIL", str(exc))

    try:
        protocols = importlib.import_module("aip.product.configured.protocols")
        economic_protocol = getattr(protocols, "EconomicIndicatorsProvider", None)
        if economic_protocol is None:
            raise RuntimeError("EconomicIndicatorsProvider protocol is not registered in runtime")
        economic_provider = container.resolve(economic_protocol)
        _print_check("Economic indicators provider", "PASS", type(economic_provider).__name__)
    except Exception as exc:
        failures.append(f"Economic indicators provider: {exc}")
        _print_check("Economic indicators provider", "FAIL", str(exc))

    print()
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f" - {item}")

    if failures:
        print("DEEP RUNTIME CERTIFICATION: FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("DEEP RUNTIME CERTIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
