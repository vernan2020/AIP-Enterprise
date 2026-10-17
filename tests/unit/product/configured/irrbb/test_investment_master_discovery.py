from __future__ import annotations

from datetime import date

from aip.product.configured.irrbb.investment_master_discovery import (
    find_exact_cutoff_master,
)


def test_exact_master_is_chosen_only_at_requested_cutoff(tmp_path):
    root = tmp_path / "Inversiones" / "2026" / "maestro" / "09"
    root.mkdir(parents=True)
    (root / "29-09-2026.xlsx").write_text("not read", encoding="utf-8")
    pattern = r"Inversiones\{year}\maestro\{month}\*.xls*"
    cutoff = date(2026, 9, 30)
    assert find_exact_cutoff_master(str(tmp_path), pattern, cutoff) == (
        "EXACT_CUTOFF_MASTER_NOT_FOUND",
        0,
    )
    (root / "30-09-2026.xlsx").write_text("not read", encoding="utf-8")
    assert find_exact_cutoff_master(str(tmp_path), pattern, cutoff) == (
        "EXACT_CUTOFF_MASTER_FOUND_NOT_CERTIFIED",
        1,
    )
    (root / "30-09-2026.xls").write_text("not read", encoding="utf-8")
    assert find_exact_cutoff_master(str(tmp_path), pattern, cutoff) == (
        "AMBIGUOUS_MASTER_FILES",
        2,
    )


def test_master_discovery_fails_closed_for_bad_config(tmp_path):
    cutoff = date(2026, 9, 30)
    assert find_exact_cutoff_master(None, "*.xlsx", cutoff)[0] == "UNCONFIGURED"
    assert find_exact_cutoff_master(str(tmp_path), "../*.xlsx", cutoff)[0] == ("INVALID_PATTERN")
    assert find_exact_cutoff_master(str(tmp_path), "{unknown}", cutoff)[0] == ("INVALID_PATTERN")
