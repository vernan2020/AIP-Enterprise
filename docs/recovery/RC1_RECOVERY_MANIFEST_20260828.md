# RC1 Recovery Manifest — 2026-08-28

Branch: `recovery/local-rc1-20260828`
Base: `release/core-v1.0`

This manifest records the canonical recovered local artifacts that remain to be synchronized as complete files. The SHA-256 hashes below are computed from the sanitized working copy recovered from the user's RC1 backup. They are intended to prevent accidental partial reconstruction of large production files during recovery.

## Large production files pending full synchronization

| Path | Bytes | SHA-256 |
|---|---:|---|
| `src/aip/product/configured/adapters/configured_portfolio_provider.py` | 48672 | `626bf8ac02cd3992895d39b7acfdcd76dec3114afe8753e597cd7a7915dc2ca9` |
| `src/aip/product/configured/adapters/configured_market_provider.py` | 23773 | `45edf8adef92ba9455c51833e400cd9f2e5dca5a65fcf1dd1537b4acc84cf5ad` |
| `src/aip/product/configured/adapters/configured_liquidity_provider.py` | 28676 | `4c7ef50773c7be00475bf2c8f683e29de4a13847c021427e3968faa41d9a8e68` |
| `src/aip/product/configured/services/configured_portfolio_var_service.py` | 51134 | `37ef70a7d328f1d6a2629200776332ae2c4989e87f2b707e3e7286012fa49011` |
| `src/aip/ui/shell/main_window.py` | 45165 | `b86dec86fee2c8feaebec6c0435728f82789c72256071f8ea48c7658e22435d5` |
| `src/aip/ui/modules/macro_intelligence/views/macro_intelligence_view.py` | 32129 | `a6190980e4fe925c3e35c6b7825b87d61f4610f476d7df331e45d064ca53e496` |

## Recovery rules

1. Do not reconstruct the files above from snippets or partial diffs.
2. Preserve the VeR result cache and lazy Master/PiPCA repository behavior in `ConfiguredPortfolioVaRService`.
3. Preserve the shared `ValuationDateContext` wiring for Portfolio, Market, Liquidity and VeR.
4. Preserve Macro Intelligence snapshot-first, asynchronous BCCR refresh and stale-on-error behavior.
5. Exclude `.venv`, `__pycache__`, `.pytest_cache`, DuckDB runtime databases, backup files and diagnostic dumps from production recovery commits.

## Current local hardening after manifest hash

The recovered Macro Intelligence view was additionally hardened so a refresh requested while a BCCR worker is running is coalesced and executed immediately after the active worker finishes. This prevents a valuation-date change from being silently skipped during an in-flight macro refresh. The Macro file hash above already includes this hardening.

The recovered MainWindow was additionally hardened so the Treasury route injects `TreasuryPresenter(self._demo_factory)` instead of constructing `TreasuryView()` with an implicit presenter/factory. This prevents the production shell from creating a second independent `DemoApplicationFactory` when Treasury is opened. The MainWindow hash above includes this hardening and preserves the source file's CRLF line endings.

## Important branch state

The recovery branch is intentionally incremental. Some already-synchronized composition files reference services that are listed above and are still pending complete synchronization. Treat the branch as a recovery work branch until this manifest is fully cleared; do not merge it into `release/core-v1.0` before the pending files are synchronized and validation is complete.
