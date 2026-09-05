from __future__ import annotations

from datetime import date

from aip.domain.financial_analysis.models import (
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_capital_adequacy_matrix_reader import (
    SUGEFCapitalAdequacyMatrixReader,
)
from aip.product.configured.readers.sugef_capital_adequacy_reader import (
    SUGEFCapitalAdequacyReader,
)
from aip.product.configured.readers.sugef_credit_quality_reader import (
    SUGEFCreditQualityReader,
)
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFFinancialApiClient,
)
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
    SUGEFFinancialStatementReader,
)
from aip.product.configured.readers.sugef_liquidity_indicator_reader import (
    SUGEFLiquidityIndicatorReader,
)
from aip.product.configured.readers.sugef_official_financial_api_client import (
    SUGEFOfficialFinancialApiClient,
)


class SUGEFOfficialFinancialStatementReader(SUGEFFinancialStatementReader):
    """Lector productivo que admite únicamente fuentes oficiales SUGEF.

    A diferencia del lector de compatibilidad histórica, este adaptador nunca
    incorpora la matriz CSV institucional incluida en el paquete. Puede combinar
    la API pública con exportaciones SUGEF colocadas explícitamente en la ruta
    configurada, conservando trazabilidad por registro.

    La calidad de cartera y la liquidez se calculan desde reportes oficiales
    SUGEF y se alinean al último corte que tenga Balance + Estado de Resultados.
    La suficiencia patrimonial se toma de la publicación trimestral oficial más
    reciente cuyo corte sea anterior o igual al corte contable. Ninguna de estas
    fuentes desplaza el corte contable principal de la calificación.
    """

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFFinancialApiClient | None = None,
        credit_quality_reader: SUGEFCreditQualityReader | None = None,
        liquidity_reader: SUGEFLiquidityIndicatorReader | None = None,
        capital_adequacy_reader: SUGEFCapitalAdequacyReader | None = None,
    ) -> None:
        super().__init__(
            config,
            api_client=api_client or SUGEFOfficialFinancialApiClient(config),
        )
        self._credit_quality_reader = credit_quality_reader or SUGEFCreditQualityReader(config)
        self._liquidity_reader = liquidity_reader or SUGEFLiquidityIndicatorReader(config)
        self._capital_adequacy_reader = capital_adequacy_reader or SUGEFCapitalAdequacyMatrixReader(
            config
        )

    def read(self, *, cutoff_date: date | None = None) -> SUGEFFinancialReadResult:
        paths = self._discover_files()
        diagnostics: list[str] = []
        lines: list[FinancialStatementLine] = []
        api_endpoints: set[str] = set()

        if self._config.enabled and self._config.api_enabled and cutoff_date is not None:
            api_result = self._api_client.read(cutoff_date)
            lines.extend(api_result.lines)
            api_endpoints.update(api_result.endpoints)
            diagnostics.extend(api_result.diagnostics)

            accounting_cutoff = self._primary_accounting_cutoff(tuple(lines)) or cutoff_date

            credit_result = self._credit_quality_reader.read(accounting_cutoff)
            lines.extend(credit_result.lines)
            api_endpoints.update(credit_result.endpoints)
            diagnostics.extend(credit_result.diagnostics)

            liquidity_result = self._liquidity_reader.read(
                accounting_cutoff,
                include_all_entities=True,
            )
            lines.extend(liquidity_result.lines)
            api_endpoints.update(liquidity_result.source_files)
            diagnostics.extend(liquidity_result.diagnostics)

            capital_result = self._capital_adequacy_reader.read(accounting_cutoff)
            lines.extend(capital_result.lines)
            api_endpoints.update(capital_result.source_files)
            diagnostics.extend(capital_result.diagnostics)

            if accounting_cutoff != cutoff_date:
                diagnostics.append(
                    "Indicadores SUGEF derivados alineados al último corte contable completo: "
                    f"{accounting_cutoff.strftime('%d/%m/%Y')}."
                )

        for path in paths:
            try:
                lines.extend(self._read_file(path, diagnostics))
            except Exception as exc:
                diagnostics.append(f"{path.name}: no se pudo leer ({type(exc).__name__}: {exc})")

        endpoints = tuple(sorted(api_endpoints))
        if not lines:
            diagnostics.append(
                "No se obtuvieron datos oficiales SUGEF desde la API ni desde exportaciones "
                "configuradas; no se utiliza información de respaldo."
            )
        elif endpoints and paths:
            diagnostics.append(
                "Fuente consolidada exclusivamente con API pública SUGEF y exportaciones "
                "oficiales configuradas."
            )
        elif endpoints:
            diagnostics.append("Fuente activa: publicaciones y API pública oficial de SUGEF.")
        else:
            diagnostics.append("Fuente activa: exportaciones oficiales SUGEF configuradas.")

        if not paths and self._config.root and not endpoints:
            diagnostics.append(
                "No se encontraron exportaciones SUGEF compatibles en la ruta configurada."
            )
        elif not paths and not self._config.root and not endpoints:
            diagnostics.append(
                "No existe una ruta SUGEF local configurada y la API no aportó datos."
            )

        return SUGEFFinancialReadResult(
            lines=tuple(lines),
            source_files=(*endpoints, *(str(path) for path in paths)),
            diagnostics=tuple(diagnostics),
            fingerprint=self._fingerprint(paths, cutoff_date=cutoff_date),
        )

    def fingerprint(self, *, cutoff_date: date | None = None) -> str:
        return self._fingerprint(self._discover_files(), cutoff_date=cutoff_date)

    def _primary_accounting_cutoff(
        self,
        lines: tuple[FinancialStatementLine, ...],
    ) -> date | None:
        if not self._config.api_entity_codes:
            return None
        primary = self._config.api_entity_codes[0]
        balance_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.BALANCE_SHEET
        }
        income_dates = {
            line.statement_date
            for line in lines
            if line.entity.entity_id == primary
            and line.statement_type is FinancialStatementType.INCOME_STATEMENT
        }
        common = balance_dates & income_dates
        return max(common) if common else None
