from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import (
    SUGEFPublicApiResponse,
)
from aip.product.configured.readers.sugef_trial_balance_reader import (
    SUGEFTrialBalanceReader,
)


class _TrialBalanceApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, str]] = []

    @staticmethod
    def _row(
        *,
        entity_code: str,
        entity_name: str,
        account_code: str,
        account_name: str,
        balance: str | None,
    ) -> dict[str, object]:
        return {
            "codigoSector": 7,
            "descripcionSector": "COOPERATIVAS DE AHORRO Y CREDITO",
            "codigoEntidad": entity_code,
            "nombreEntidad": entity_name,
            "periodo": "2026-07-01T00:00:00",
            "cuentaCatalogoSugef": account_code,
            "codigoTipoCatalogo": 14.0,
            "nombreCuenta": account_name,
            "nivelCuenta": 3.0,
            "saldoFinal": balance,
        }

    def read_financial_entity_report(
        self,
        report_name: str,
        *,
        entity_code: str,
        periods: str,
        account_code: str = "",
    ) -> SUGEFPublicApiResponse:
        self.calls.append((report_name, entity_code, periods, account_code))
        if entity_code == "3004045138":
            rows = (
                self._row(
                    entity_code="3004045138",
                    entity_name="COOPEALIANZA R.L.",
                    account_code="10000000.0",
                    account_name="Disponibilidades",
                    balance="100.50",
                ),
                self._row(
                    entity_code="3004045138",
                    entity_name="COOPEALIANZA R.L.",
                    account_code="12000000",
                    account_name="Inversiones en instrumentos financieros",
                    balance=None,
                ),
            )
        else:
            rows = (
                # Debe excluirse porque Coopealianza ya se consultó directamente.
                self._row(
                    entity_code="3004045138",
                    entity_name="COOPEALIANZA R.L.",
                    account_code="10000000",
                    account_name="Disponibilidades",
                    balance="9999",
                ),
                self._row(
                    entity_code="3004045001",
                    entity_name="COOPERATIVA PAR",
                    account_code="10000000",
                    account_name="Disponibilidades",
                    balance="75",
                ),
            )
        return SUGEFPublicApiResponse(
            operation="/ReportesFinancieraContable/MAPI/ReporteBalanzaComprobacionEntidad",
            endpoint=f"https://sugef.example/balanza/{entity_code or 'all'}",
            method="POST",
            body={"listaReporteBalanzaComprobacionEntidad": list(rows)},
            rows=rows,
        )


def test_trial_balance_reader_gets_all_accounts_and_preserves_null_balance() -> None:
    api = _TrialBalanceApi()
    reader = SUGEFTrialBalanceReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert len(result.lines) == 2
    availability, investments = result.lines
    assert availability.statement_date == date(2026, 7, 31)
    assert availability.account_code == "10000000"
    assert availability.catalog_type_code == "14"
    assert availability.ending_balance == Decimal("100.50")
    assert investments.ending_balance is None
    assert (
        "ReporteBalanzaComprobacionEntidad",
        "3004045138",
        "20260701",
        "",
    ) in api.calls
    assert any("1 saldos publicados como nulos" in item for item in result.diagnostics)


def test_trial_balance_reader_can_add_sfn_peers_without_double_counting_primary_entity() -> None:
    api = _TrialBalanceApi()
    reader = SUGEFTrialBalanceReader(
        SUGEFFinancialSourceConfig(api_entity_codes=("3004045138",)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31), include_all_entities=True)

    primary = [line for line in result.lines if line.entity_code == "3004045138"]
    peers = [line for line in result.lines if line.entity_code == "3004045001"]
    assert len(primary) == 2
    assert len(peers) == 1
    assert peers[0].ending_balance == Decimal("75")
    assert (
        "ReporteBalanzaComprobacionEntidad",
        "",
        "20260701",
        "",
    ) in api.calls
