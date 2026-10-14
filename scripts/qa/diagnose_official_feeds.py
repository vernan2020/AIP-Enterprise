"""Read-only, credential-safe operational diagnosis of official SUGEF and BCCR.

Only prints statuses and record counts. It neither copies databases nor logs
tokens, emails, entity names, source URLs, HTTP bodies or request payloads.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import replace
from datetime import date, timedelta

from aip.integration.bccr.providers.urllib_http_provider import UrllibHTTPProvider
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFFinancialApiClient,
)
from aip.product.demo.configuration.environment_loader import EnvironmentLoader


def _outcome(error: Exception) -> str:
    """No exception text: URLs and proxy diagnostics can contain private data."""
    from urllib.error import HTTPError, URLError

    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, URLError):
        return "RED/TLS/DNS NO DISPONIBLE"
    if isinstance(error, TimeoutError):
        return "TIMEOUT"
    if isinstance(error, OSError):
        return "ERROR DE RED O SISTEMA"
    if isinstance(error, ValueError):
        return "RESPUESTA NO INTERPRETABLE"
    return f"ERROR {type(error).__name__}"


def _records(payload: object, expected_key: str) -> int:
    """Return only the count of records from an official public response."""
    if not isinstance(payload, dict):
        return 0
    if payload.get("tieneError") is True:
        return 0
    value = payload.get(expected_key)
    if isinstance(value, list):
        return len(value)
    # Older API variants use a differently cased list name.
    for key, value in payload.items():
        if key.casefold() == expected_key.casefold() and isinstance(value, list):
            return len(value)
    return 0


def _period_coverage(payload: object, expected_key: str, *, target_date: date) -> str:
    """Summarize returned accounting months, not just HTTP success.

    Neither identifiers nor monetary amounts leave the diagnostic process.
    """
    if not isinstance(payload, dict):
        return "RESPUESTA INVÁLIDA"
    if payload.get("tieneError") is True:
        return "ERROR DE RESPUESTA"
    rows = payload.get(expected_key)
    if not isinstance(rows, list):
        rows = next(
            (
                value
                for key, value in payload.items()
                if key.casefold() == expected_key.casefold() and isinstance(value, list)
            ),
            None,
        )
    if not isinstance(rows, list):
        return "ESQUEMA INESPERADO"
    months: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = str(row.get("periodo") or "")
        month = raw[:7] if len(raw) >= 7 and raw[4] == "-" else raw[:6]
        if len(month) == 6 and month.isdigit():
            month = month[:4] + "-" + month[4:]
        if len(month) == 7 and month[:4].isdigit() and month[5:7].isdigit():
            months.add(month)
    expected = f"{target_date:%Y-%m}"
    if expected in months:
        return f"CORTE {expected} PRESENTE"
    if months:
        return f"CORTE {expected} AUSENTE; último devuelto {max(months)}"
    return "SIN FECHAS CONTABLES EN LA RESPUESTA"


def _bccr_fx_coverage(body: object) -> str:
    """Check actual FX series dates, never treat a nonempty error as success."""
    if not isinstance(body, dict) or body.get("estado") is not True:
        return "RESPUESTA OFICIAL NO EXITOSA"
    charts = body.get("datos")
    if not isinstance(charts, list):
        return "ESQUEMA INESPERADO"

    coverage: dict[str, list[date]] = {"317": [], "318": []}
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        indicators = chart.get("indicadores")
        if not isinstance(indicators, list):
            continue
        for indicator in indicators:
            if not isinstance(indicator, dict):
                continue
            code = str(indicator.get("codigoIndicador", ""))
            if code not in coverage or not isinstance(indicator.get("series"), list):
                continue
            for observation in indicator["series"]:
                if not isinstance(observation, dict):
                    continue
                try:
                    observed = date.fromisoformat(str(observation.get("fecha", ""))[:10])
                except ValueError:
                    continue
                coverage[code].append(observed)

    def describe(code: str, name: str) -> str:
        dates = coverage[code]
        return (
            f"{name}: {len(dates)} obs; último {max(dates):%Y-%m-%d}"
            if dates
            else f"{name}: SIN OBSERVACIONES"
        )

    return f"{describe('317', 'compra')}; {describe('318', 'venta')}"


def _bccr_individual_coverage(body: object, code: str) -> str:
    """Summarize one officially published series without leaking monetary amounts."""
    if not isinstance(body, dict) or body.get("estado") is not True:
        return "RESPUESTA OFICIAL NO EXITOSA"
    series = body.get("datos")
    if not isinstance(series, list):
        return "ESQUEMA INESPERADO"
    dates: list[date] = []
    for indicator in series:
        if not isinstance(indicator, dict):
            continue
        if str(indicator.get("codigoIndicador", "")) != code:
            continue
        for item in indicator.get("series", ()):
            if not isinstance(item, dict):
                continue
            try:
                dates.append(date.fromisoformat(str(item.get("fecha", ""))[:10]))
            except ValueError:
                continue
    return (
        f"{len(dates)} obs; último {max(dates):%Y-%m-%d}"
        if dates
        else "SIN OBSERVACIONES"
    )


def _bccr_probe(config: object, *, target_date: date, indicator_code: str | None = None) -> str:
    token = getattr(config, "token", None)
    route = f"BCCR indicador {indicator_code}" if indicator_code else "BCCR cuadro 1"
    if not token:
        return "BCCR: CREDENCIAL NO VISIBLE EN ESTA SESIÓN (NO SE CONSULTÓ)"
    from aip.integration.bccr.configuration.bccr_config import BCCRConfig
    from aip.integration.bccr.connector.rest_client import BCCRRestClient

    try:
        client = BCCRRestClient(
            config=BCCRConfig(
                base_url=getattr(config, "base_url", None) or "https://apim.bccr.fi.cr",
                timeout_seconds=12.0,
                token=token,
            ),
            provider=UrllibHTTPProvider(),
        )
        start = (target_date - timedelta(days=14)).strftime("%Y/%m/%d")
        end = target_date.strftime("%Y/%m/%d")
        request_url = (
            client.build_url(indicator_code=indicator_code, from_date=start, to_date=end)
            if indicator_code
            else client.build_chart_url(chart_code="1", from_date=start, to_date=end)
        )
        # A single request, no exponential retries; identical credential/header
        # contract to the production BCCRRestClient.
        response = UrllibHTTPProvider().get(
            request_url,
            timeout=12.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        status = int(response.get("status_code", 0))
        body = response.get("body")
        coverage = (
            _bccr_individual_coverage(body, indicator_code)
            if indicator_code
            else _bccr_fx_coverage(body)
        )
        return f"{route}: HTTP {status}; {coverage}"
    except Exception as exc:
        return f"{route}: {_outcome(exc)}"


def _bccr_metadata_probe(config: object) -> str:
    """Isolate SDDE gateway access from the economic-series processing backend.

    The endpoint is documented by BCCR; never return the URL, HTTP body, token
    or any identity-related field in diagnostics.
    """
    token = getattr(config, "token", None)
    if not token:
        return "BCCR metadatos cuadro 1: TOKEN NO VISIBLE"
    base_url = (getattr(config, "base_url", None) or "https://apim.bccr.fi.cr").rstrip("/")
    url = (
        f"{base_url}/SDDE/api/Bccr.GE.SDDE.Publico.Indicadores.API/"
        "cuadro/1/metadata?idioma=ES"
    )
    try:
        response = UrllibHTTPProvider().get(
            url,
            timeout=12.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        code = int(response.get("status_code", 0))
        body = response.get("body")
        valid = isinstance(body, dict) and body.get("estado") is True
        return (
            f"BCCR metadatos cuadro 1: HTTP {code}; "
            + ("RESPUESTA EXITOSA" if code == 200 and valid else "NO CONFIRMADA")
        )
    except Exception as exc:
        return f"BCCR metadatos cuadro 1: {_outcome(exc)}"


def _sugef_probe(config: object, *, target_date: date) -> tuple[str, ...]:
    if not getattr(config, "enabled", False) or not getattr(config, "api_enabled", False):
        return ("SUGEF: API DESHABILITADA EN CONFIGURACIÓN EFECTIVA",)
    codes = getattr(config, "api_entity_codes", ())
    if not codes:
        return ("SUGEF: SIN CÓDIGO DE ENTIDAD PARA CONSULTA",)
    api = SUGEFFinancialApiClient(
        replace(config, api_timeout_seconds=12.0, api_retries=0)
    )
    period = target_date.strftime("%Y%m01")
    reports = (
        ("BALANZA", "ReporteBalanzaComprobacionEntidad", "listaBalanzaComprobacionEntidad"),
        (
            "BALANCE CONTABLE",
            "ReporteBalanceSituacionContableDespuesMarzo2020Entidad",
            "listaBalanceSituacionContableEntidad",
        ),
        (
            "RESULTADOS CONTABLES",
            "ReporteEstadoResultadosContableDespuesMarzo2020Entidad",
            "listaEstadoResultadosContableEntidad",
        ),
    )
    messages: list[str] = []
    for label, report, key in reports:
        try:
            payload = {
                "parametrosEntidad": {
                    "codigoEntidad": codes[0],
                    "periodos": period,
                    "codigoCuenta": "",
                }
            }
            result = api._post_json(api._endpoint(report), payload)
            count = _records(result, key)
            coverage = _period_coverage(result, key, target_date=target_date)
            messages.append(
                f"SUGEF {label} {target_date:%Y-%m}: "
                f"{count} registros; {coverage}"
            )
        except Exception as exc:
            messages.append(
                f"SUGEF {label} {target_date:%Y-%m}: {_outcome(exc)}"
            )
    return tuple(messages)


def diagnose(*, period: date, live: bool) -> list[str]:
    env = os.environ
    config = EnvironmentLoader().load_source_config()
    status = [
        "AIP CONFIGURED - DIAGNÓSTICO OFICIAL SIN CAMBIOS",
        f"Corte SUGEF consultado: {period:%Y-%m}",
        "BCCR token: " + ("PRESENTE" if config.bccr.token else "NO VISIBLE"),
        "BCCR conector: " + ("HABILITADO" if config.bccr.enabled else "DESHABILITADO"),
        "SUGEF API: " + ("HABILITADA" if config.sugef_financial.api_enabled else "DESHABILITADA"),
        "SUGEF entidad: "
        + ("CONFIGURADA" if config.sugef_financial.api_entity_codes else "NO CONFIGURADA"),
        "Configuración local: "
        + ("VARIABLE DEFINIDA" if env.get("AIP_RUNTIME_LOCAL_CMD") else "SIN OVERRIDE EXTERNO"),
    ]
    if not live:
        return status + ["Pruebas de red omitidas; utilice --live para verificar fuentes oficiales."]
    if config.bccr.enabled:
        status.append(_bccr_metadata_probe(config.bccr))
        status.append(_bccr_probe(config.bccr, target_date=date.today()))
        status.append(_bccr_probe(config.bccr, target_date=date.today(), indicator_code="317"))
    status.extend(_sugef_probe(config.sugef_financial, target_date=period))
    status.append("FIN - nunca se guardaron credenciales ni respuestas.")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico seguro BCCR y SUGEF")
    parser.add_argument("--live", action="store_true", help="Consultar APIs con credenciales configuradas")
    parser.add_argument("--period", default="2026-09", help="Período SUGEF YYYY-MM")
    args = parser.parse_args(argv)
    try:
        period = date.fromisoformat(args.period + "-01")
        for line in diagnose(period=period, live=args.live):
            print(line)
    except Exception as exc:
        # Never include raw exception messages from URL/config loading.
        print("No se completó el diagnóstico: " + _outcome(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
