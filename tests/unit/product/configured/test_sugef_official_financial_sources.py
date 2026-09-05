from __future__ import annotations

from datetime import date
from urllib.error import URLError

from aip.domain.financial_analysis.models import FinancialStatementType
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
)
from aip.product.configured.readers.sugef_official_financial_statement_reader import (
    SUGEFOfficialFinancialStatementReader,
)

_PEERS = (
    ("3004045138", "COOPEALIANZA R.L."),
    ("3004000001", "COOPERATIVA PAR 1"),
    ("3004000002", "COOPERATIVA PAR 2"),
)
_ACCOUNT_NAMES = {
    "10000": "ACTIVO TOTAL",
    "25000": "PATRIMONIO TOTAL",
    "30000": "RESULTADO FINAL",
    "31000": "RESULTADO OPERACIONAL BRUTO",
    "31300": "RESULTADO INTERMEDIACION FINANCIERA",
    "32000": "GASTOS DE ADMINISTRACION",
}


class _OfficialStubClient(SUGEFOfficialFinancialApiClient):
    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)
        self.indicator_entity_codes: list[str] = []
        self.requests: list[tuple[str, str, str]] = []
        self.filtered_requests: list[tuple[str, str, str, str]] = []

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
    def _entities(entity_code: str) -> tuple[tuple[str, str], ...]:
        if entity_code == "":
            return _PEERS
        return tuple(item for item in _PEERS if item[0] == entity_code)

    @staticmethod
    def _account_row(
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
        period = str(parameters["periodos"])
        account_code = str(parameters["codigoCuenta"])
        report = (
            "BALANCE"
            if "BalanceSituacion" in endpoint
            else "INCOME" if "EstadoResultados" in endpoint else "INDICATORS"
        )
        self.requests.append((entity_code, report, period))
        if account_code:
            self.filtered_requests.append((entity_code, report, period, account_code))

        if report in {"BALANCE", "INCOME"}:
            default_account = "10000" if report == "BALANCE" else "30000"
            resolved_account = account_code or default_account
            entities = self._entities(entity_code)
            rows = [
                self._account_row(
                    entity_code=code,
                    entity_name=name,
                    period=period_token,
                    account_code=resolved_account,
                    amount=800_000_000_000 + entity_index + period_index,
                )
                for period_index, period_token in enumerate(self._period_tokens(period))
                for entity_index, (code, name) in enumerate(entities)
            ]
            list_key = (
                "listaBalanceSituacionAnalisisFinancieroEntidad"
                if report == "BALANCE"
                else "listaEstadoResultadosAnalisisFinancieroEntidad"
            )
            return {"tieneError": False, list_key: rows}

        self.indicator_entity_codes.append(entity_code)
        peers = self._entities(entity_code)
        values = {
            "3004045138": 1.10,
            "3004000001": 0.90,
            "3004000002": 1.30,
        }
        return {
            "tieneError": False,
            "listaIndicadoresFinancierosEntidad": [
                {
                    "codigoSector": "6",
                    "descripcionSector": "Cooperativas",
                    "codigoEntidad": code,
                    "nombreEntidad": name,
                    "periodo": "2026-07-01T00:00:00",
                    "codigoIndicador": "ROA",
                    "nombreIndicador": "ROA",
                    "valorIndicador": values[code],
                }
                for code, name in peers
            ],
        }


class _PeerIndicatorFailureStubClient(_OfficialStubClient):
    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        parameters = payload["parametrosEntidad"]
        assert isinstance(parameters, dict)
        if str(parameters["codigoEntidad"]) == "" and "IndicadoresFinancieros" in endpoint:
            raise URLError("peer indicator endpoint unavailable")
        return super()._post_json(endpoint, payload)


class _PublicationLagStubClient(_OfficialStubClient):
    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        parameters = payload["parametrosEntidad"]
        assert isinstance(parameters, dict)
        entity_code = str(parameters["codigoEntidad"])
        period = str(parameters["periodos"])
        if entity_code == "3004045138" and period == "20260801" and "BalanceSituacion" in endpoint:
            self.requests.append((entity_code, "BALANCE", period))
            raise URLError("August accounting cutoff not published")
        return super()._post_json(endpoint, payload)


def test_official_api_uses_direct_entity_and_blank_entity_for_indicators() -> None:
    client = _OfficialStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    assert client.indicator_entity_codes == ["3004045138", ""]
    indicator_lines = tuple(
        line for line in result.lines if line.statement_type is FinancialStatementType.INDICATORS
    )
    assert {line.entity.entity_id for line in indicator_lines} == {code for code, _ in _PEERS}
    peer_balances = tuple(
        line
        for line in result.lines
        if line.statement_type is FinancialStatementType.BALANCE_SHEET
        and line.statement_date == date(2026, 7, 31)
    )
    assert {line.entity.entity_id for line in peer_balances} == {code for code, _ in _PEERS}
    assert any("universo comparativo SFN" in message for message in result.diagnostics)


def test_official_api_requests_filtered_methodology_history_for_sfn_peers() -> None:
    client = _OfficialStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    blank_filtered = {
        (report, account_code)
        for entity_code, report, _period, account_code in client.filtered_requests
        if entity_code == ""
    }
    assert blank_filtered == {
        ("BALANCE", "10000"),
        ("BALANCE", "25000"),
        ("INCOME", "30000"),
        ("INCOME", "31000"),
        ("INCOME", "31300"),
        ("INCOME", "32000"),
    }
    assert len([request for request in client.filtered_requests if request[0] == ""]) == 6
    assert ("", "INDICATORS", "20260701") in client.requests
    assert ("3004045138", "INDICATORS", "20260701") in client.requests

    for code, _ in _PEERS:
        balance_dates = {
            line.statement_date
            for line in result.lines
            if line.entity.entity_id == code
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
            and line.account_code == "10000"
        }
        assert len(balance_dates) == 12
        assert min(balance_dates) == date(2025, 8, 31)
        assert max(balance_dates) == date(2026, 7, 31)


def test_direct_entity_indicator_survives_peer_indicator_failure() -> None:
    client = _PeerIndicatorFailureStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    primary_indicators = tuple(
        line
        for line in result.lines
        if line.entity.entity_id == "3004045138"
        and line.statement_type is FinancialStatementType.INDICATORS
    )
    assert any(line.account_name == "ROA" for line in primary_indicators)
    assert any(
        "ReporteIndicadoresFinancierosEntidad (SFN completo)" in message
        for message in result.diagnostics
    )


def test_official_api_falls_back_to_latest_complete_accounting_cutoff() -> None:
    client = _PublicationLagStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 8, 31))

    assert result.lines
    assert max(line.statement_date for line in result.lines) == date(2026, 7, 31)
    assert ("3004045138", "BALANCE", "20260801") in client.requests
    assert ("3004045138", "BALANCE", "20260701") in client.requests
    assert ("3004045138", "INDICATORS", "20260701") in client.requests
    assert ("3004045138", "INDICATORS", "20260801") not in client.requests
    assert any(
        "Corte solicitado en AIP: 31/08/2026" in message and "31/07/2026" in message
        for message in result.diagnostics
    )
    assert all(
        "August accounting cutoff not published" not in message for message in result.diagnostics
    )


def test_report_range_continues_with_prior_month_after_api_error() -> None:
    client = _PublicationLagStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    lines, _ = client._read_report(
        "3004045138",
        "20250901-20260801",
        *client._BALANCE_REPORT,
    )

    assert lines
    assert ("3004045138", "BALANCE", "20250901-20260801") in client.requests
    assert ("3004045138", "BALANCE", "20250801-20260701") in client.requests


def test_official_reader_never_activates_bundled_reference_matrix() -> None:
    reader = SUGEFOfficialFinancialStatementReader(
        SUGEFFinancialSourceConfig(api_enabled=False, root=None)
    )

    result = reader.read(cutoff_date=date(2026, 7, 31))

    assert result.lines == ()
    assert result.source_files == ()
    assert any("no se utiliza información de respaldo" in message for message in result.diagnostics)
    assert all("referencia institucional" not in message for message in result.diagnostics)
