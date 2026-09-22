from __future__ import annotations

import pytest

from aip.product.configured.irrbb.credit_xml_currency_catalog import (
    CreditXMLCurrencyCatalog,
    CreditXMLCurrencyCodeBinding,
)
from aip.shared.money import Currency


def _catalog() -> CreditXMLCurrencyCatalog:
    return CreditXMLCurrencyCatalog(
        code="TEST-CREDIT-CURRENCY",
        version="1",
        evidence_reference="TEST:EVIDENCE:CATALOG",
        bindings=(
            CreditXMLCurrencyCodeBinding(
                source_code="SRC-MN",
                currency=Currency.CRC,
                evidence_reference="TEST:EVIDENCE:SRC-MN",
            ),
            CreditXMLCurrencyCodeBinding(
                source_code="SRC-ME",
                currency=Currency.USD,
                evidence_reference="TEST:EVIDENCE:SRC-ME",
            ),
        ),
    )


def test_catalog_resolves_only_explicit_governed_bindings() -> None:
    catalog = _catalog()

    assert catalog.resolve("SRC-MN") is Currency.CRC
    assert catalog.resolve("SRC-ME") is Currency.USD


def test_catalog_has_no_default_mapping_for_observed_numeric_source_codes() -> None:
    catalog = _catalog()

    with pytest.raises(KeyError, match="unmapped credit XML currency source code: 1"):
        catalog.resolve("1")

    with pytest.raises(KeyError, match="unmapped credit XML currency source code: 2"):
        catalog.resolve("2")


def test_catalog_rejects_duplicate_source_codes() -> None:
    binding = CreditXMLCurrencyCodeBinding(
        source_code="SRC-MN",
        currency=Currency.CRC,
        evidence_reference="TEST:EVIDENCE:A",
    )

    with pytest.raises(ValueError, match="source codes must be unique"):
        CreditXMLCurrencyCatalog(
            code="TEST-CREDIT-CURRENCY",
            version="1",
            evidence_reference="TEST:EVIDENCE:CATALOG",
            bindings=(
                binding,
                CreditXMLCurrencyCodeBinding(
                    source_code="SRC-MN",
                    currency=Currency.USD,
                    evidence_reference="TEST:EVIDENCE:B",
                ),
            ),
        )


def test_catalog_requires_versioned_evidence_and_nonempty_bindings() -> None:
    with pytest.raises(ValueError, match="code is required"):
        CreditXMLCurrencyCatalog(
            code=" ",
            version="1",
            evidence_reference="TEST:EVIDENCE",
            bindings=(
                CreditXMLCurrencyCodeBinding(
                    source_code="A",
                    currency=Currency.CRC,
                    evidence_reference="TEST:EVIDENCE:A",
                ),
            ),
        )

    with pytest.raises(ValueError, match="version is required"):
        CreditXMLCurrencyCatalog(
            code="TEST",
            version=" ",
            evidence_reference="TEST:EVIDENCE",
            bindings=(
                CreditXMLCurrencyCodeBinding(
                    source_code="A",
                    currency=Currency.CRC,
                    evidence_reference="TEST:EVIDENCE:A",
                ),
            ),
        )

    with pytest.raises(ValueError, match="requires at least one binding"):
        CreditXMLCurrencyCatalog(
            code="TEST",
            version="1",
            evidence_reference="TEST:EVIDENCE",
            bindings=(),
        )


def test_binding_rejects_noncanonical_or_unevidenced_source_code() -> None:
    with pytest.raises(ValueError, match="must be canonical text"):
        CreditXMLCurrencyCodeBinding(
            source_code=" 1 ",
            currency=Currency.CRC,
            evidence_reference="TEST:EVIDENCE",
        )

    with pytest.raises(ValueError, match="evidence_reference is required"):
        CreditXMLCurrencyCodeBinding(
            source_code="1",
            currency=Currency.CRC,
            evidence_reference=" ",
        )


def test_resolve_rejects_blank_or_padded_runtime_source_codes() -> None:
    catalog = _catalog()

    with pytest.raises(ValueError, match="source code is required"):
        catalog.resolve(" ")

    with pytest.raises(ValueError, match="must be canonical text"):
        catalog.resolve(" SRC-MN ")
