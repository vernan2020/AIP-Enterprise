from __future__ import annotations

from datetime import date

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
)

_PRIMARY = "3004045138"
_PEERS = (
    (_PRIMARY, "COOPEALIANZA R.L."),
    ("3004000001", "COOPERATIVA PAR 1"),
    ("3004000002", "COOPERATIVA PAR 2"),
    ("3004000003", "COOPERATIVA PAR 3"),
)
_ACCOUNT_NAMES = {
    "10000": "ACTIVO TOTAL",
    "25000": "PATRIMONIO TOTAL",
    "30000": "RESULTADO FINAL",
    "31000": "RESULTADO OPERACIONAL BRUTO",
    "31300": "RESULTADO INTERMEDIACION FINANCIERA",
    "32000": "GASTOS DE ADMINISTRACION",
}


class _FilteredHistoryStub(SUGEFOfficialFinancialApiClient):
    def __init__(self) -> None:
        super().__init__(
            SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=(_PRIMARY,))
        )
        self.requests: list[tuple[str, str, str, str]] = []

    @staticmethod
    def _period_tokens(periods: str) -> tuple[str, ...]:
        if "-" in periods:
            start_text, end_text = periods.split("-", 1)
            start = date(int(start_text[:4]), int(start_text[4:6]), 1)
            end = date(int(end_text[:4]), int(end_text[4:6]), 1)
            values: list[str] = []
            current = start
            while current <= end:
                values.append(f"{current:%Y%m%d}")
                current = SUGEFOfficialFinancialApiClient._shift_month(current, 1)
            return tuple(values)
        return tuple(token for token in periods.split(",") if token)

    @staticmethod
    def _row(
        *,
        entity_code: str,
        entity_name: str,
        period: str,
        account_code: str,
        amount: float,
    ) -> dict[str, object]:
        return {
            "codigoSector": "6",
            "descripcionSector": "Cooperativas",
            "codigoEntidad": entity_code,
            "nombreEntidad": entity_name,
            "periodo": f"{period[:4]}-{period[4:6]}-01T00:00:00",
            "cuentaIASEF": account_code,
            "nombreCuenta": _ACCOUNT_NAMES[account_code],
            "saldoIASEF": amount,
        }

    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        parameters = payload["parametrosEntidad"]
        assert isinstance(parameters, dict)
        entity_code = str(parameters["codigoEntidad"])
        periods = str(parameters["periodos"])
        account_code = str(parameters["codigoCuenta"])
        report = (
            "BALANCE"
            if "BalanceSituacion" in endpoint
            else "INCOME" if "EstadoResultados" in endpoint else "INDICATORS"
        )
        self.requests.append((entity_code, report, periods, account_code))

        if report == "INDICATORS":
            entities = _PEERS if entity_code == "" else (_PEERS[0],)
            return {
                "tieneError": False,
                "listaIndicadoresFinancierosEntidad": [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": code,
                        "nombreEntidad": name,
                        "periodo": "2026-07-01T00:00:00",
                        "codigoIndicador": "81000",
                        "nombreIndicador": "ROE",
                        "valorIndicador": 10.0,
                    }
                    for code, name in entities
                ],
            }

        entities = _PEERS if entity_code == "" else (_PEERS[0],)
        if not account_code:
            account_code = "10000" if report == "BALANCE" else "30000"
        rows = [
            self._row(
                entity_code=code,
                entity_name=name,
                period=period,
                account_code=account_code,
                amount=1000.0 + index,
            )
            for period in self._period_tokens(periods)
            for index, (code, name) in enumerate(entities)
        ]
        list_key = (
            "listaBalanceSituacionAnalisisFinancieroEntidad"
            if report == "BALANCE"
            else "listaEstadoResultadosAnalisisFinancieroEntidad"
        )
        return {"tieneError": False, list_key: rows}


def test_methodology_history_uses_six_filtered_bulk_queries_and_reuses_probe() -> None:
    client = _FilteredHistoryStub()

    result = client.read(date(2026, 7, 31))

    assert result.lines
    assert all(
        client._has_methodology_history(list(result.lines), code, date(2026, 7, 31))
        for code, _ in _PEERS[1:]
    )

    blank_history = [
        request
        for request in client.requests
        if request[0] == "" and request[1] in {"BALANCE", "INCOME"}
    ]
    assert len(blank_history) == 6
    assert {request[3] for request in blank_history} == {
        "10000",
        "25000",
        "30000",
        "31000",
        "31300",
        "32000",
    }
    assert all(request[3] for request in blank_history)

    primary_unfiltered_balance = [
        request
        for request in client.requests
        if request[0] == _PRIMARY and request[1] == "BALANCE" and request[3] == ""
    ]
    primary_unfiltered_income = [
        request
        for request in client.requests
        if request[0] == _PRIMARY and request[1] == "INCOME" and request[3] == ""
    ]
    assert len(primary_unfiltered_balance) == 1
    assert len(primary_unfiltered_income) == 1
    assert any("Historia 08ME14-01 optimizada" in message for message in result.diagnostics)


def test_mass_direct_peer_recovery_is_suppressed() -> None:
    client = _FilteredHistoryStub()
    lines = []
    endpoints: set[str] = set()
    diagnostics: list[str] = []

    for index in range(client._MAX_DIRECT_PEER_RECOVERY + 1):
        code = f"9000{index:06d}"
        line = client._line(
            {
                "codigoSector": "6",
                "descripcionSector": "Cooperativas",
                "codigoEntidad": code,
                "nombreEntidad": f"PAR {index}",
                "periodo": "2026-07-01T00:00:00",
                "codigoIndicador": "81000",
                "nombreIndicador": "ROE",
                "valorIndicador": 10.0,
            },
            client._INDICATOR_REPORT[2],
            "https://sugef.example/indicators",
            client._INDICATOR_REPORT[1],
            index + 1,
        )
        assert line is not None
        lines.append(line)

    client._recover_incomplete_peer_history(
        date(2026, 7, 31),
        lines,
        endpoints,
        diagnostics,
    )

    assert any("exceden el máximo seguro" in message for message in diagnostics)
    assert client.requests == []
