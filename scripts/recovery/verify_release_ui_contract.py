from __future__ import annotations

from pathlib import Path


_UI_CONTRACT: dict[str, tuple[str, ...]] = {
    "src/aip/ui/modules/portfolio/views/portfolio_view.py": (
        'self._tabs.addTab(self._history, "Histórico KPIs")',
        'self._tabs.addTab(self._valuation_comparison, "Ganancia / pérdida")',
        'self._tabs.addTab(page, "Posiciones")',
    ),
    "src/aip/ui/modules/portfolio/widgets/portfolio_history_line_chart.py": (
        "def _draw_latest_value_pill(",
        "def _draw_hover_card(",
        "def _draw_time_axis(",
        "def _time_axis_label(",
        "def _smooth_path(",
    ),
    "src/aip/ui/modules/portfolio/views/portfolio_valuation_comparison_view.py": (
        "class PortfolioValuationComparisonView",
        "portfolioValuationShowAll",
        "Valuación acumulada",
    ),
}


def verify_runtime_ui_contract(root: Path) -> tuple[str, ...]:
    """Return deterministic failures when the live source predates the release UI."""

    failures: list[str] = []
    for relative_path, required_markers in _UI_CONTRACT.items():
        path = root / relative_path
        if not path.is_file():
            failures.append(f"missing:{relative_path}")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for marker in required_markers:
            if marker not in content:
                failures.append(f"stale:{relative_path}:{marker}")
    return tuple(failures)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    failures = verify_runtime_ui_contract(root)
    if failures:
        print("AIP RELEASE UI CONTRACT: STALE_OR_INCOMPLETE")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("AIP RELEASE UI CONTRACT: CURRENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
