from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_complete_peer_financial_api_client import (
    SUGEFCompletePeerFinancialApiClient,
)
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult


_CUTOFF = date(2026, 7, 31)
_LIABILITY_ACCOUNT = "22222"


class _PeerLiabilityClient(SUGEFCompletePeerFinancialApiClient):
    def __init__(self) -> None:
        super().__init__(SUGEFFinancialSourceConfig(api_entity_codes=("PRIMARY",)))
        self.requested_account: str | None = None

    def _read_filtered_report(
        self,
        entity_code: str,
        period: str,
        report_name: str,
        list_key: str,
        statement_type: FinancialStatementType,
        account_code: str,
    ) -> tuple[list[FinancialStatementLine], str]:
        del period, report_name, list_key
        assert entity_code == ""
        assert statement_type is FinancialStatementType.BALANCE_SHEET
        self.requested_account = account_code
        return (
            [
                _line(
                    "PEER-1",
                    FinancialStatementType.BALANCE_SHEET,
                    account_code,
                    "PASIVO TOTAL",
                    "80",
                ),
                _line(
                    "PEER-2",
                    FinancialStatementType.BALANCE_SHEET,
                    account_code,
                    "PASIVO TOTAL",
                    "120",
                ),
            ],
            "test://sugef/liabilities",
        )


def _line(
    entity_id: str,
    statement_type: FinancialStatementType,
    account_code: str,
    account_name: str,
    amount: str,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        entity=FinancialEntity(entity_id, f"Entidad {entity_id}"),
        statement_date=_CUTOFF,
        statement_type=statement_type,
        account_code=account_code,
        account_name=account_name,
        amount=Decimal(amount),
    )


def test_peer_liabilities_use_source_native_account_from_primary_balance() -> None:
    client = _PeerLiabilityClient()
    result = SUGEFApiReadResult(
        lines=(
            _line(
                "PRIMARY",
                FinancialStatementType.BALANCE_SHEET,
                _LIABILITY_ACCOUNT,
                "TOTAL PASIVO",
                "100",
            ),
            _line(
                "PRIMARY",
                FinancialStatementType.INCOME_STATEMENT,
                "30000",
                "RESULTADO",
                "10",
            ),
        ),
        endpoints=("test://sugef/primary",),
        diagnostics=(),
    )

    enriched = client._supplement_peer_liabilities(result)

    assert client.requested_account == _LIABILITY_ACCOUNT
    peer_ids = {
        line.entity.entity_id
        for line in enriched.lines
        if line.account_code == _LIABILITY_ACCOUNT
        and line.entity.entity_id.startswith("PEER-")
    }
    assert peer_ids == {"PEER-1", "PEER-2"}
    assert "test://sugef/liabilities" in enriched.endpoints
    assert any("Pasivos comparativos SFN" in message for message in enriched.diagnostics)


def test_peer_liabilities_fail_closed_when_primary_balance_has_no_total_pasivo() -> None:
    client = _PeerLiabilityClient()
    result = SUGEFApiReadResult(
        lines=(
            _line(
                "PRIMARY",
                FinancialStatementType.BALANCE_SHEET,
                "10000",
                "ACTIVO TOTAL",
                "100",
            ),
            _line(
                "PRIMARY",
                FinancialStatementType.INCOME_STATEMENT,
                "30000",
                "RESULTADO",
                "10",
            ),
        ),
        endpoints=("test://sugef/primary",),
        diagnostics=(),
    )

    enriched = client._supplement_peer_liabilities(result)

    assert client.requested_account is None
    assert enriched.lines == result.lines
    assert any("conserva N/D" in message for message in enriched.diagnostics)
