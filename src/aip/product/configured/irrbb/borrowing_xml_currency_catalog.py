from __future__ import annotations

from dataclasses import dataclass

from aip.shared.money import Currency


@dataclass(frozen=True, slots=True)
class BorrowingXMLCurrencyCodeBinding:
    """One institutionally evidenced Obligaciones XML currency-code binding."""

    source_code: str
    currency: Currency
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.source_code.strip():
            raise ValueError("Obligaciones XML currency source_code is required")
        if self.source_code != self.source_code.strip():
            raise ValueError("Obligaciones XML currency source_code must be canonical text")
        if not self.evidence_reference.strip():
            raise ValueError("Obligaciones XML currency evidence_reference is required")


@dataclass(frozen=True, slots=True)
class BorrowingXMLCurrencyCatalog:
    """Versioned, fail-closed translation of Obligaciones source currency codes.

    No default source-code mapping exists. Production callers must inject bindings
    supported by institutional evidence before a source amount can cross the
    canonical currency boundary.
    """

    code: str
    version: str
    evidence_reference: str
    bindings: tuple[BorrowingXMLCurrencyCodeBinding, ...]

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("Obligaciones XML currency catalog code is required")
        if not self.version.strip():
            raise ValueError("Obligaciones XML currency catalog version is required")
        if not self.evidence_reference.strip():
            raise ValueError("Obligaciones XML currency catalog evidence_reference is required")
        if not self.bindings:
            raise ValueError("Obligaciones XML currency catalog requires at least one binding")

        source_codes = tuple(binding.source_code for binding in self.bindings)
        if len(source_codes) != len(set(source_codes)):
            raise ValueError("Obligaciones XML currency catalog source codes must be unique")

    def resolve(self, source_code: str) -> Currency:
        """Resolve one exact governed source code without fallback or inference."""

        normalized = source_code.strip()
        if not normalized:
            raise ValueError("Obligaciones XML currency source code is required")
        if source_code != normalized:
            raise ValueError("Obligaciones XML currency source code must be canonical text")

        for binding in self.bindings:
            if binding.source_code == normalized:
                return binding.currency

        raise KeyError(f"unmapped Obligaciones XML currency source code: {normalized}")
