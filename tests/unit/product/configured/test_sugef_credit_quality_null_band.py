from __future__ import annotations

from datetime import date

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReader,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiResponse

_ENTITY = "3004045138"


class _NullBandApi:
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
        del report_name, sector_code, periods, regulation, days_arrears, historical
        rows = []
        if entity_code in {_ENTITY, ""}:
            for band, amount in {
                "1": "900",
                "2": "20",
                "3": "20",
                "4": "10",
                "5": "20",
                "6": "20",
                "7": None,
            }.items():
                rows.append(
                    {
                        "codigoEntidad": _ENTITY,
                        "aliasPublicacionEntidad": "COOPEALIANZA R.L.",
                        "nombreTipoEntidad": "Cooperativas",
                        "periodo": "2026-07-01T00:00:00",
                        "normativa": "1",
                        "maximoAtraso": band,
                        "saldoPrincipal": amount,
                    }
                )
        return SUGEFPublicApiResponse(
            operation="/ReporteCrediticio/MAPI/ReporteDiasAtraso",
            endpoint="https://sugef.example/ReporteDiasAtraso",
            method="POST",
            body={"listaReporteDiasAtraso": rows},
            rows=tuple(rows),
        )


def test_explicit_null_band_is_never_converted_to_zero() -> None:
    reader = SUGEFCreditQualityReader(
        SUGEFFinancialSourceConfig(api_entity_codes=(_ENTITY,)),
        api_client=_NullBandApi(),  # type: ignore[arg-type]
    )

    result = reader.read(date(2026, 7, 31))

    assert result.lines == ()
    assert any(
        "JUDICIAL_COLLECTION" in message
        and "saldo principal es nulo o inválido" in message
        and "se conserva N/D" in message
        for message in result.diagnostics
    )
