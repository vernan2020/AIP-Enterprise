"""Characterize canonical and legacy shared-module identity during migration."""

from __future__ import annotations

import importlib


def test_validation_legacy_alias_resolves_to_canonical_module() -> None:
    canonical = importlib.import_module("aip.shared.validation")
    legacy = importlib.import_module("src.aip.shared.validation")

    assert legacy is canonical


def test_validation_exceptions_legacy_alias_resolves_to_canonical_module() -> None:
    importlib.import_module("aip.shared.validation")
    canonical = importlib.import_module("aip.shared.validation.exceptions")
    legacy = importlib.import_module("src.aip.shared.validation.exceptions")

    assert legacy is canonical


def test_money_legacy_alias_resolves_to_canonical_module() -> None:
    canonical = importlib.import_module("aip.shared.money")
    legacy = importlib.import_module("src.aip.shared.money")

    assert legacy is canonical
