from __future__ import annotations

from types import SimpleNamespace

from aip.product.configured.irrbb.investment_source_selection import (
    select_investment_source,
)


def _master(*, certified: bool, count: int, failures: int = 0):
    return SimpleNamespace(
        certification=SimpleNamespace(
            status=SimpleNamespace(value="READY" if certified else "BLOCKED"),
            is_ready=certified,
        ),
        snapshot=SimpleNamespace(
            position_records=tuple(range(count)),
            mapping_failures=tuple(range(failures)),
        ),
    )


def test_certified_master_is_only_investment_position_source() -> None:
    decision = select_investment_source(_master(certified=True, count=3))
    assert decision.status == "READY"
    assert decision.canonical_positions == 3
    assert decision.source == "INSTITUTIONAL_PORTFOLIO_MASTER"
    assert decision.reconciliation_source == "Crediticio_InversionesActivas.xml"


def test_uncertified_master_never_falls_back_to_investment_xml() -> None:
    decision = select_investment_source(_master(certified=False, count=3))
    assert decision.status == "BLOCKED"
    assert decision.canonical_positions == 0


def test_missing_or_unmapped_positions_are_not_silently_certified() -> None:
    for count, failures in ((0, 0), (2, 1)):
        decision = select_investment_source(_master(certified=True, count=count, failures=failures))
        assert decision.status == "BLOCKED"
        assert decision.canonical_positions == 0
