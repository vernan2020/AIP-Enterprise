from __future__ import annotations

from pathlib import Path

from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def _exists(path: str | None) -> bool:
    return bool(path and Path(path).exists())


def main() -> int:
    loader = EnvironmentLoader()
    config = loader.load()
    sources = loader.load_source_config()

    print("AIP CONFIGURED PREFLIGHT")
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

    if failures:
        print("Status: FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("Status: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
