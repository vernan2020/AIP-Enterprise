from __future__ import annotations

from datetime import date

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


class _OfficialStubClient(SUGEFOfficialFinancialApiClient):
    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        super().__init__(config)
        self.indicator_entity_codes: list[str] = []

    def _post_json(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        parameters = payload["parametrosEntidad"]
        assert isinstance(parameters, dict)
        entity_code = str(parameters["codigoEntidad"])

        if "BalanceSituacion" in endpoint:
            assert entity_code == "3004045138"
            return {
                "tieneError": False,
                "listaBalanceSituacionAnalisisFinancieroEntidad": [
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
                ],
            }

        if "EstadoResultados" in endpoint:
            assert entity_code == "3004045138"
            return {
                "tieneError": False,
                "listaEstadoResultadosAnalisisFinancieroEntidad": [
                    {
                        "codigoSector": "6",
                        "descripcionSector": "Cooperativas",
                        "codigoEntidad": "3004045138",
                        "nombreEntidad": "COOPEALIANZA R.L.",
                        "periodo": "2026-07-01T00:00:00",
                        "cuentaIASEF": "30000",
                        "nombreCuenta": "RESULTADO FINAL",
                        "saldoIASEF": 8_000_000_000,
                    }
                ],
            }

        self.indicator_entity_codes.append(entity_code)
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
                    "valorIndicador": value,
                }
                for code, name, value in (
                    ("3004045138", "COOPEALIANZA R.L.", 1.10),
                    ("3004000001", "COOPERATIVA PAR 1", 0.90),
                    ("3004000002", "COOPERATIVA PAR 2", 1.30),
                )
            ],
        }


def test_official_api_uses_blank_entity_for_sfn_indicator_universe() -> None:
    client = _OfficialStubClient(
        SUGEFFinancialSourceConfig(api_retries=0, api_entity_codes=("3004045138",))
    )

    result = client.read(date(2026, 7, 31))

    assert client.indicator_entity_codes == [""]
    indicator_lines = tuple(
        line for line in result.lines if line.statement_type is FinancialStatementType.INDICATORS
    )
    assert {line.entity.entity_id for line in indicator_lines} == {
        "3004045138",
        "3004000001",
        "3004000002",
    }
    assert any("todas las entidades" in message for message in result.diagnostics)


def test_official_reader_never_activates_bundled_reference_matrix() -> None:
    reader = SUGEFOfficialFinancialStatementReader(
        SUGEFFinancialSourceConfig(api_enabled=False, root=None)
    )

    result = reader.read(cutoff_date=date(2026, 7, 31))

    assert result.lines == ()
    assert result.source_files == ()
    assert any("no se utiliza información de respaldo" in message for message in result.diagnostics)
    assert all("referencia institucional" not in message for message in result.diagnostics)
