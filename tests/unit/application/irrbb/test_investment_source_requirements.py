from __future__ import annotations

from pathlib import Path

from aip.application.irrbb.investment_source_requirements import (
    INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE,
    INVESTMENT_SOURCE_REQUIREMENT_PROFILE_REFERENCE,
    INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION,
    investment_source_requirement_profile,
)


def test_investment_requirement_profile_has_resolvable_governed_reference() -> None:
    profile = investment_source_requirement_profile()

    assert profile.code == INVESTMENT_SOURCE_REQUIREMENT_PROFILE_CODE
    assert profile.version == INVESTMENT_SOURCE_REQUIREMENT_PROFILE_VERSION
    assert profile.source_reference == INVESTMENT_SOURCE_REQUIREMENT_PROFILE_REFERENCE
    assert not Path(profile.source_reference).is_absolute()

    repository_root = Path(__file__).resolve().parents[4]
    evidence_reference = repository_root / profile.source_reference

    assert evidence_reference.is_file()
    document = evidence_reference.read_text(encoding="utf-8")
    assert profile.code in document
    assert profile.version in document
    assert "production activation" in document.casefold()
    assert "fail-closed" in document.casefold()
