"""Spawned workers have no Streamlit session or institutional environment configuration."""

import json
import os
from dataclasses import replace
from datetime import date


def personal_source(settings):
    from aip.product.configured.configuration.configured_source_config import (
        BCCRSourceConfig,
        ConfiguredSourceConfig,
    )

    source = ConfiguredSourceConfig()
    return replace(
        source,
        bccr=BCCRSourceConfig(
            enabled=bool(settings.get("token")),
            base_url="https://apim.bccr.fi.cr",
            token=settings.get("token"),
            email=settings.get("email"),
            name="TicoTrader Atlas",
            timeout_seconds=20,
            retries=1,
        ),
        sugef_financial=replace(source.sugef_financial, api_timeout_seconds=25, api_retries=1),
    )


def compute(pipe, query, settings):
    for name in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    try:
        from ticotrader_web.contracts import clean
        from ticotrader_web.runtime import Runtime

        runtime = Runtime(source_config=personal_source(settings))
        kind = query["kind"]

        def as_date(value):
            return date.fromisoformat(value) if value else None

        if kind == "financial":
            data = runtime.financial(query["entity_id"], as_date(query["cutoff"]), query["refresh"])
        elif kind == "compare":
            data = runtime.compare(
                query["entity_ids"],
                query["series_code"],
                query["horizon"],
                as_date(query["custom_from"]),
                as_date(query["custom_to"]),
            )
        elif kind == "macro":
            data = runtime.macro(query["refresh"])
        elif kind == "projection":
            data = runtime.projection()
        else:
            from aip.product.configured.services.configured_advanced_macro_forecasting_service import (
                ConfiguredAdvancedMacroForecastingService,
            )
            from ticotrader_streamlit.history import forecast_service

            runtime.factory.container.register_instance(
                ConfiguredAdvancedMacroForecastingService,
                forecast_service(settings, query["indicator"]),
            )
            data = runtime.forecast(query["indicator"], query["refresh"])
        payload = json.dumps({"data": clean(data)}, ensure_ascii=False)
        for secret in (settings.get("token"), settings.get("email")):
            if secret:
                payload = payload.replace(json.dumps(secret)[1:-1], "[OCULTO]")
        encoded = payload.encode()
        if len(encoded) > 4 * 1024**2:
            encoded = b'{"error":"Resultado demasiado grande"}'
        pipe.send_bytes(encoded)
    except Exception:
        pipe.send_bytes(b'{"error":"Consulta no disponible"}')
    finally:
        pipe.close()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    class Output:
        def send_bytes(self, value):
            Path(sys.argv[1]).write_bytes(value)

        def close(self):
            pass

    request = json.load(sys.stdin)
    compute(Output(), request["query"], request["settings"])
