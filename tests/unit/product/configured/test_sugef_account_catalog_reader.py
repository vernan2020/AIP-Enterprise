from __future__ import annotations

from decimal import Decimal

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_account_catalog_reader import (
    SUGEFAccountCatalogReader,
)
from aip.product.configured.readers.sugef_public_api_client import (
    SUGEFPublicApiResponse,
)


class _CatalogApi:
    def list_account_catalog(self) -> SUGEFPublicApiResponse:
        rows = (
            {
                "cuentaCatalogoSugef": "001230000.0",
                "codigoTipoCatalogo": 14.0,
                "nombreTipoCatalogo": "CATALOGO 2024",
                "cuentaPadre": "001200000",
                "nombreCuenta": "Estimación por deterioro de cartera de crédito",
                "nivelCuenta": 3.0,
                "signo": None,
            },
            {
                "cuentaCatalogoSugef": "002100000",
                "codigoTipoCatalogo": "14",
                "nombreTipoCatalogo": "CATALOGO 2024",
                "cuentaPadre": "002000000",
                "nombreCuenta": "Obligaciones con el público",
                "nivelCuenta": "2.0",
                "signo": -1,
            },
            {
                "cuentaCatalogoSugef": "999999999",
                "codigoTipoCatalogo": "14",
                "nombreCuenta": "",
            },
        )
        return SUGEFPublicApiResponse(
            operation="/Catalogo/MAPI/ListarCatalogoCuentasContables",
            endpoint="https://sugef.example/catalog",
            method="GET",
            body={"listaCatalogoCuentasContables": list(rows)},
            rows=rows,
        )


def test_catalog_reader_preserves_codes_nulls_and_catalog_identity() -> None:
    reader = SUGEFAccountCatalogReader(
        SUGEFFinancialSourceConfig(),
        api_client=_CatalogApi(),  # type: ignore[arg-type]
    )

    result = reader.read()

    assert len(result.entries) == 2
    estimate, obligations = result.entries
    assert estimate.account_code == "001230000"
    assert estimate.catalog_type_code == "14"
    assert estimate.parent_account_code == "001200000"
    assert estimate.level == Decimal("3.0")
    assert estimate.sign is None
    assert obligations.sign == -1
    assert result.endpoint == "https://sugef.example/catalog"
    assert any("1 filas omitidas" in item for item in result.diagnostics)


def test_catalog_candidate_search_is_accent_insensitive_and_does_not_auto_select() -> None:
    reader = SUGEFAccountCatalogReader(
        SUGEFFinancialSourceConfig(),
        api_client=_CatalogApi(),  # type: ignore[arg-type]
    )
    entries = reader.read().entries

    candidates = reader.find_candidates(
        entries,
        "estimacion",
        "credito",
        catalog_type_code="14",
    )

    assert len(candidates) == 1
    assert candidates[0].account_code == "001230000"
    assert reader.find_candidates(entries, "cartera", catalog_type_code="99") == ()
