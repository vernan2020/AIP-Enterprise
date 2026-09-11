from __future__ import annotations

from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReader,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiResponse

_PRIMARY = "3004045138"
_PEER = "3004001021"
_ABSENT_PEER = "BCT"


class _PeerRecoveryApi:
    def __init__(self, *, recover_absent_peer: bool = True) -> None:
        self.recover_absent_peer = recover_absent_peer
        self.calls: list[tuple[str, str]] = []

    @staticmethod
    def _rows(
        entity_code: str,
        entity_name: str,
        *,
        missing_band: str | None = None,
    ) -> list[dict[str, str]]:
        balances = {
            "1": "950",
            "2": "15",
            "3": "10",
            "4": "5",
            "5": "10",
            "6": "10",
            "7": "0",
        }
        return [
            {
                "codigoEntidad": entity_code,
                "aliasPublicacionEntidad": entity_name,
                "nombreTipoEntidad": "ORGANIZACIONES COOPERATIVAS DE AHORRO Y CREDITO",
                "periodo": "2026-07-01T00:00:00",
                "normativa": "1",
                "maximoAtraso": band,
                "saldoPrincipal": amount,
            }
            for band, amount in balances.items()
            if band != missing_band
        ]

    def read_credit_report(
        self,
        report_name: str,
        *,
        entity_code: str = "",
        sector_code: str = "",
        periods: str,
        regulation: str = "1",
        days_arrears: str | None = None,
        historical: bool = False,
    ) -> SUGEFPublicApiResponse:
        del report_name, sector_code, periods, days_arrears, historical
        self.calls.append((entity_code, regulation))

        if entity_code == _PRIMARY:
            rows = self._rows(_PRIMARY, "COOPEALIANZA R.L.")
        elif entity_code == "":
            rows = [
                *self._rows(_PRIMARY, "COOPEALIANZA R.L."),
                *self._rows(_PEER, "COOPERATIVA PAR R.L.", missing_band="7"),
            ]
        elif entity_code == _PEER:
            rows = self._rows(_PEER, "COOPERATIVA PAR R.L.", missing_band="7")
        elif entity_code == _ABSENT_PEER and self.recover_absent_peer:
            rows = self._rows(_ABSENT_PEER, "BANCO BCT")
        else:
            rows = []

        return SUGEFPublicApiResponse(
            operation="/ReporteCrediticio/MAPI/ReporteDiasAtraso",
            endpoint="https://sugef.example/ReporteDiasAtraso",
            method="POST",
            body={"listaReporteDiasAtraso": rows},
            rows=tuple(rows),
        )


def test_peer_with_omitted_zero_band_gets_current_portfolio_indicator() -> None:
    api = _PeerRecoveryApi()
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_PRIMARY,)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    peer_indicators = {
        line.account_code: line.amount
        for line in result.lines
        if line.entity.entity_id == _PEER
        and line.statement_type is FinancialStatementType.INDICATORS
    }

    assert peer_indicators["CALC:CURRENT_PORTFOLIO"] == Decimal("950") / Decimal("1000")
    assert peer_indicators["CALC:DELINQUENCY_90"] == Decimal("20") / Decimal("1000")
    assert (_PEER, "1") in api.calls
    assert any(
        "COOPERATIVA PAR R.L." in message
        and "JUDICIAL_COLLECTION" in message
        and "saldo cero" in message
        for message in result.diagnostics
    )


def test_peer_absent_from_sfn_bulk_is_recovered_from_direct_official_query() -> None:
    api = _PeerRecoveryApi()
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_PRIMARY,)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=(_PRIMARY, _PEER, _ABSENT_PEER),
    )

    bct = {
        line.account_code: line.amount
        for line in result.lines
        if line.entity.entity_id == _ABSENT_PEER
    }
    assert bct == {
        "CALC:CURRENT_PORTFOLIO": Decimal("0.95"),
        "CALC:DELINQUENCY_90": Decimal("0.02"),
    }
    assert (_ABSENT_PEER, "") in api.calls
    assert any(
        _ABSENT_PEER in message and "barrido SFN" in message for message in result.diagnostics
    )


def test_peer_absent_from_bulk_and_direct_query_remains_unavailable() -> None:
    api = _PeerRecoveryApi(recover_absent_peer=False)
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_PRIMARY,)),
        api_client=api,  # type: ignore[arg-type]
    )

    result = reader.read(
        date(2026, 7, 31),
        expected_entity_codes=(_PRIMARY, _ABSENT_PEER),
    )

    assert all(line.entity.entity_id != _ABSENT_PEER for line in result.lines)
    assert (_ABSENT_PEER, "") in api.calls
    assert any(
        _ABSENT_PEER in message and "permanece N/D" in message for message in result.diagnostics
    )
