from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError, URLError

from aip.domain.financial_analysis.credit_quality import (
    CreditAgingAmount,
    CreditAgingBand,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReader,
    _BucketRow,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


class SUGEFResilientCreditQualityReader(SUGEFCreditQualityReader):
    """Credit-quality reader with targeted fallback for omitted aging bands.

    The standard bulk and direct ``ReporteDiasAtraso`` queries remain the primary
    source. Some SUGEF responses can still omit an entity or return an individual
    ``maximoAtraso`` row with a null principal even though the same official API
    exposes a valid balance when that aging code is requested explicitly.

    This reader therefore adds one auditable fallback that follows SUGEF API v1.2:
    each unresolved aging code is re-queried through ``diasAtraso=1..7``. A value
    is accepted only when SUGEF returns a valid principal for the exact entity,
    month and normative. A zero is introduced only after a successful targeted
    request returns no row at all for that exact aging code. Explicit null or
    invalid balances remain unavailable and are never coerced to zero.
    """

    _SUGEF_CODE_BY_BAND = {
        band: code for code, band in SUGEFCreditQualityReader._BAND_BY_SUGEF_CODE.items()
    }

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFPublicApiClient | None = None,
    ) -> None:
        super().__init__(config, api_client=api_client)

    def _recover_missing_entities(
        self,
        *,
        period: str,
        buckets: tuple[_BucketRow, ...],
        expected_entity_codes: tuple[str, ...],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> tuple[_BucketRow, ...]:
        recovered = super()._recover_missing_entities(
            period=period,
            buckets=buckets,
            expected_entity_codes=expected_entity_codes,
            endpoints=endpoints,
            diagnostics=diagnostics,
        )
        observed = {row.entity.entity_id for row in recovered}
        remaining = tuple(
            sorted(
                code
                for code in set(expected_entity_codes)
                if code and code not in observed
            )
        )
        if not remaining:
            return recovered

        output = list(recovered)
        for entity_code in remaining:
            targeted: list[_BucketRow] = []
            successful_requests = 0
            for band, sugef_code in self._SUGEF_CODE_BY_BAND.items():
                del band
                try:
                    response = self._api.read_credit_report(
                        "ReporteDiasAtraso",
                        entity_code=entity_code,
                        sector_code="",
                        periods=period,
                        regulation="",
                        days_arrears=sugef_code,
                    )
                    successful_requests += 1
                    endpoints.add(response.endpoint)
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    diagnostics.append(
                        f"Entidad SUGEF {entity_code}: consulta dirigida diasAtraso="
                        f"{sugef_code} falló; se conserva N/D para esa banda. "
                        f"{type(exc).__name__}: {exc}"
                    )
                    continue
                targeted.extend(
                    row
                    for row in self._normalize_rows(response.rows, response.endpoint)
                    if row.entity.entity_id == entity_code
                )

            if targeted:
                output.extend(targeted)
                diagnostics.append(
                    f"Entidad SUGEF {entity_code}: calidad de cartera recuperada mediante "
                    "consultas dirigidas por código de días de atraso porque la consulta "
                    "general no devolvió filas utilizables."
                )
            elif successful_requests:
                diagnostics.append(
                    f"Entidad SUGEF {entity_code}: las consultas dirigidas de "
                    "ReporteDiasAtraso tampoco devolvieron saldos principales válidos; "
                    "calidad de cartera permanece N/D."
                )
        return tuple(output)

    def _recover_incomplete_normatives(
        self,
        *,
        period: str,
        buckets: tuple[_BucketRow, ...],
        endpoints: set[str],
        diagnostics: list[str],
    ) -> tuple[_BucketRow, ...]:
        grouped: dict[tuple[str, date, str], list[_BucketRow]] = defaultdict(list)
        for row in buckets:
            grouped[(row.entity.entity_id, row.statement_date, row.normative)].append(row)

        replacements: dict[tuple[str, date, str], tuple[_BucketRow, ...]] = {}
        for key, normative_rows in sorted(grouped.items()):
            entity_id, statement_date, normative = key
            initial = self._calculator.calculate(
                tuple(CreditAgingAmount(row.band, row.principal) for row in normative_rows)
            )
            if initial.complete or not initial.missing_bands:
                continue

            entity = normative_rows[0].entity
            direct_rows: tuple[_BucketRow, ...] = ()
            try:
                response = self._api.read_credit_report(
                    "ReporteDiasAtraso",
                    entity_code=entity_id,
                    sector_code="",
                    periods=period,
                    regulation=normative,
                    days_arrears="",
                )
                endpoints.add(response.endpoint)
                direct_rows = tuple(
                    row
                    for row in self._normalize_rows(response.rows, response.endpoint)
                    if row.entity.entity_id == entity_id
                    and row.statement_date == statement_date
                    and row.normative == normative
                )
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "consulta general directa de ReporteDiasAtraso falló; se intentarán "
                    f"las bandas faltantes de forma individual. {type(exc).__name__}: {exc}"
                )

            # Preserve every already-valid band from the bulk query and prefer
            # exact-entity direct values when they are available.
            rows_by_band: dict[CreditAgingBand, list[_BucketRow]] = defaultdict(list)
            for row in normative_rows:
                rows_by_band[row.band].append(row)
            for band in {row.band for row in direct_rows}:
                rows_by_band[band] = [row for row in direct_rows if row.band is band]

            unresolved = tuple(
                band for band in CreditAgingBand if not rows_by_band.get(band)
            )
            confirmed_zero: list[CreditAgingBand] = []
            invalid_reported: list[CreditAgingBand] = []
            failed_bands: list[CreditAgingBand] = []

            for band in unresolved:
                sugef_code = self._SUGEF_CODE_BY_BAND[band]
                try:
                    targeted = self._api.read_credit_report(
                        "ReporteDiasAtraso",
                        entity_code=entity_id,
                        sector_code="",
                        periods=period,
                        regulation=normative,
                        days_arrears=sugef_code,
                    )
                    endpoints.add(targeted.endpoint)
                except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                    failed_bands.append(band)
                    diagnostics.append(
                        f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                        f"consulta dirigida diasAtraso={sugef_code} falló; "
                        f"{band.value} permanece N/D. {type(exc).__name__}: {exc}"
                    )
                    continue

                valid_rows = tuple(
                    row
                    for row in self._normalize_rows(targeted.rows, targeted.endpoint)
                    if row.entity.entity_id == entity_id
                    and row.statement_date == statement_date
                    and row.normative == normative
                    and row.band is band
                )
                if valid_rows:
                    rows_by_band[band] = list(valid_rows)
                    diagnostics.append(
                        f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                        f"banda {band.value} recuperada mediante consulta oficial dirigida "
                        f"diasAtraso={sugef_code}."
                    )
                    continue

                reported = self._raw_reported_bands(
                    targeted.rows,
                    entity_id=entity_id,
                    statement_date=statement_date,
                    normative=normative,
                )
                if band in reported:
                    invalid_reported.append(band)
                    diagnostics.append(
                        f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                        f"SUGEF reportó {band.value} en consulta dirigida, pero el saldo "
                        "principal es nulo o inválido; se conserva N/D."
                    )
                    continue

                rows_by_band[band] = [
                    _BucketRow(
                        entity=entity,
                        statement_date=statement_date,
                        normative=normative,
                        band=band,
                        principal=Decimal("0"),
                        source_row=0,
                        endpoint=targeted.endpoint,
                    )
                ]
                confirmed_zero.append(band)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    f"consulta oficial dirigida diasAtraso={sugef_code} no devolvió fila "
                    f"para {band.value}; se confirma saldo cero exclusivamente para el cálculo."
                )

            recovered_rows = tuple(
                row for band in CreditAgingBand for row in rows_by_band.get(band, ())
            )
            replacements[key] = recovered_rows

            result = self._calculator.calculate(
                tuple(CreditAgingAmount(row.band, row.principal) for row in recovered_rows)
            )
            if result.complete:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "las siete bandas requeridas para calidad de cartera quedaron "
                    "reconciliadas con la API oficial SUGEF."
                )
            elif invalid_reported or failed_bands:
                remaining = ", ".join(band.value for band in result.missing_bands)
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    f"calidad de cartera permanece N/D; bandas no resueltas: {remaining}."
                )
            elif confirmed_zero:
                diagnostics.append(
                    f"{entity.name} {statement_date:%d/%m/%Y} normativa {normative}: "
                    "las bandas sin saldo fueron confirmadas mediante consultas dirigidas."
                )

        if not replacements:
            return buckets

        output = [
            row
            for row in buckets
            if (row.entity.entity_id, row.statement_date, row.normative) not in replacements
        ]
        for key in sorted(replacements):
            output.extend(replacements[key])
        return tuple(output)
