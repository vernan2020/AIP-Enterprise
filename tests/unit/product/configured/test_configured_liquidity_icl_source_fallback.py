from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aip.product.configured.adapters.configured_liquidity_provider import (
    ConfiguredLiquidityProvider,
)
from aip.product.configured.readers.institutional_icl_reader import (
    InstitutionalICLReader,
    InstitutionalICLReadResult,
)
from aip.product.demo.configuration.demo_config import DemoConfig


def _icl_result(source_file: str, valuation_date: date) -> InstitutionalICLReadResult:
    return InstitutionalICLReadResult(
        source_file=source_file,
        valuation_date=valuation_date,
        sheet_name="ICL",
        icl_total=Decimal("9.79"),
        icl_mn=Decimal("10.75"),
        icl_me=Decimal("4.38"),
        liquid_asset_fund_total=Decimal("100"),
        liquid_asset_fund_mn=Decimal("80"),
        liquid_asset_fund_me=Decimal("20"),
        total_outflows_30d_total=Decimal("20"),
        total_outflows_30d_mn=Decimal("15"),
        total_outflows_30d_me=Decimal("5"),
        total_inflows_30d_total=Decimal("10"),
        total_inflows_30d_mn=Decimal("8"),
        total_inflows_30d_me=Decimal("2"),
        net_cash_outflow_30d_total=Decimal("10"),
        net_cash_outflow_30d_mn=Decimal("7"),
        net_cash_outflow_30d_me=Decimal("3"),
    )


def test_invalid_exact_icl_uses_prior_valid_candidate_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ConfiguredLiquidityProvider(
        DemoConfig(execution_mode="CONFIGURED", demo_mode_enabled=False)
    )
    exact = Path("ICL 30 SETIEMBRE_2026.xlsx")
    prior = Path("ICL 29 SETIEMBRE_2026.xlsx")

    monkeypatch.setattr(provider, "_icl_candidates", lambda _cutoff: [exact, prior])

    def fake_read(
        _reader: InstitutionalICLReader,
        file_path: str | Path,
    ) -> InstitutionalICLReadResult:
        path = Path(file_path)
        if path == exact:
            raise ValueError("Required ICL value is missing at AA10")
        return _icl_result(path.name, date(2026, 9, 29))

    monkeypatch.setattr(InstitutionalICLReader, "read", fake_read)

    result, errors = provider._load_icl_for_cutoff(date(2026, 9, 30))

    assert result is not None
    assert result.valuation_date == date(2026, 9, 29)
    assert result.source_file == prior.name
    assert errors == [
        "ICL source rejected: ICL 30 SETIEMBRE_2026.xlsx: " "Required ICL value is missing at AA10"
    ]
