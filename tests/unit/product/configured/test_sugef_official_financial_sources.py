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


class _OfficialStubClient(SUGEFOfficialFinancialApiClient):
    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)
        self.indicator_entity_codes: list[str] = []
        self.requests: list[tuple[str, str, str]] = []

    @staticmethod
    def _iso_period(period: str, *, default: str = "20260701") -> str:
        token = period if len(period) == 8 and period.isdigit() else default
        return f"{token[:4]}-{token[4:6]}-01T00:00:00"

    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        parameters = payload["parametrosEntidad"]
        assert isinstance(parameters, dict)
        entity_code = str(parameters["codigoEntidad"])
        period = str(parameters["periodos"])
        report = (
            "BALANCE"
            if "BalanceSituacion" in endpoint
            else "INCOME" if "EstadoResultados" in endpoint else "INDICATORS"
        )
        self.requests.append((entity_code, report, period))

        if "BalanceSituacion" in endpoint:
            if entity_code == "":
                statement_period = self._iso_period(period)
                rows = [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": code,
                        "nombreEntidad": name,
                        "periodo": statement_period,
                        "cuentaIASEF": "10000",
                        "nombreCuenta": "ACTIVO TOTAL",
                        "saldoIASEF": 500_000_000_000 + index,
                    }
                    for index, (code, name) in enumerate(_PEERS)
                ]
            else:
                assert entity_code == "3004045138"
                rows = [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": "3004045138",
                        "nombreEntidad": "COOPEALIANZA R.L.",
                        "periodo": f"{year:04d}-{month:02d}-01T00:00:00",
                        "cuentaIASEF": "10000",
                        "nombreCuenta": "ACTIVO TOTAL",
                        "saldoIASEF": 800_000_000_000 + index,
                    }
                    for index, (year, month) in enumerate(
                        (
                            (2025, 8),
                            (2025, 9),
                            (2025, 10),
                            (2025, 11),
                            (2025, 12),
                            (2026, 1),
                            (2026, 2),
                            (2026, 3),
                            (2026, 4),
                            (2026, 5),
                            (2026, 6),
                            (2026, 7),
                        )
                    )
                ]
            return {
                "tieneError": False,
                "listaBalanceSituacionAnalisisFinancieroEntidad": rows,
            }

        if "EstadoResultados" in endpoint:
            peers = _PEERS if entity_code == "" else (_PEERS[0],)
            statement_period = (
                self._iso_period(period) if entity_code == "" else "2026-07-01T00:00:00"
            )
            return {
                "tieneError": False,
                "listaEstadoResultadosAnalisisFinancieroEntidad": [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": code,
                        "nombreEntidad": name,
                        "periodo": statement_period,
                        "cuentaIASEF": "30000",
                        "nombreCuenta": "RESULTADO FINAL",
                        "saldoIASEF": 8_000_000_000 + index,
                    }
                    for index, (code, name) in enumerate(peers)
                ],
            }

        self.indicator_entity_codes.append(entity_code)
        peers = _PEERS if entity_code == "" else (_PEERS[0],)
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
        if (
            entity_code == "3004045138"
            and "20260801" in period
            and "BalanceSituacion" in endpoint
        ):
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


def test_official_api_requests_monthly_methodology_history_for_sfn_peers() -> None:
    client = _OfficialStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    peer_balance_requests = {
        period
        for entity_code, report, period in client.requests
        if entity_code == "" and report == "BALANCE"
    }
    assert peer_balance_requests == set(client._peer_balance_periods(date(2026, 7, 31)))

    peer_income_requests = {
        period
        for entity_code, report, period in client.requests
        if entity_code == "" and report == "INCOME"
    }
    assert peer_income_requests == set(client._peer_income_periods(date(2026, 7, 31)))
    assert ("", "INDICATORS", "20260701") in client.requests
    assert ("3004045138", "INDICATORS", "20260701") in client.requests

    for code, _ in _PEERS:
        balance_dates = {
            line.statement_date
            for line in result.lines
            if line.entity.entity_id == code
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
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
        "Corte solicitado en AIP: 31/08/2026" in message
        and "31/07/2026" in message
        for message in result.diagnostics
    )
    assert all("August accounting cutoff not published" not in message for message in result.diagnostics)


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
