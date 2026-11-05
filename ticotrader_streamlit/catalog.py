"""Official entity names for independent financial page selectors."""

import streamlit as st

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient

COMPARISON_SERIES = {
    "ASSETS": "Activos",
    "LOANS": "Cartera de crédito",
    "LIABILITIES": "Pasivos",
    "EQUITY": "Patrimonio",
    "NET_INCOME": "Resultado neto",
    "ROA": "ROA",
    "ROE": "ROE",
}


def entity_options(rows):
    options = {}
    for row in rows:
        code = str(row.get("codigoEntidad") or "").strip()
        name = str(row.get("nombreEntidad") or "").strip()
        if code and name:
            options[code] = name
    return dict(sorted(options.items(), key=lambda item: (item[1].casefold(), item[0])))


@st.cache_data(ttl=3600, max_entries=1, show_spinner=False)
def load_entities():
    config = SUGEFFinancialSourceConfig(api_timeout_seconds=12, api_retries=0)
    options = entity_options(SUGEFPublicApiClient(config).list_entities().rows)
    if not options:
        raise ValueError("El catálogo oficial no contiene entidades disponibles.")
    return options
