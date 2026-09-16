from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace

from aip.application.irrbb import IRRBBAnalysisRequest, IRRBBAnalysisResult
from aip.domain.irrbb.models import IRRBBInstrumentClass
from aip.ui.modules.rate_risk.models import (
    RateRiskReadModel,
    RateRiskSourceMappingFailureRow,
    RateRiskSourceSummaryRow,
)
from aip.ui.modules.rate_risk.presenters.rate_risk_presenter import (
    RateRiskPresenter as _BaseRateRiskPresenter,
)


class RateRiskPresenter(_BaseRateRiskPresenter):
    """Extend the certified RTILB presenter with source diagnostics.

    The base presenter remains responsible for financial and canonical data-quality
    presentation. This extension only exposes information already produced by the
    source anti-corruption layer: mapping failures and a cross-currency-safe count
    of canonical positions by banking-book segment. No source inference, monetary
    aggregation or financial calculation is performed here.
    """

    _SEGMENT_LABELS = {
        IRRBBInstrumentClass.CREDIT: "Crédito",
        IRRBBInstrumentClass.TERM_DEPOSIT: "Captaciones · Certificados",
        IRRBBInstrumentClass.BORROWING: "Obligaciones con Entidades",
        IRRBBInstrumentClass.INVESTMENT: "Inversiones",
        IRRBBInstrumentClass.NON_MATURITY_DEPOSIT: "Captaciones · No vencimiento",
        IRRBBInstrumentClass.OFF_BALANCE: "Fuera de balance",
        IRRBBInstrumentClass.OTHER: "Otros",
    }
    _SEGMENT_ORDER = {
        IRRBBInstrumentClass.CREDIT: 0,
        IRRBBInstrumentClass.TERM_DEPOSIT: 1,
        IRRBBInstrumentClass.BORROWING: 2,
        IRRBBInstrumentClass.INVESTMENT: 3,
        IRRBBInstrumentClass.NON_MATURITY_DEPOSIT: 4,
        IRRBBInstrumentClass.OFF_BALANCE: 5,
        IRRBBInstrumentClass.OTHER: 6,
    }

    @classmethod
    def build_from_analysis(
        cls,
        *,
        request: IRRBBAnalysisRequest,
        result: IRRBBAnalysisResult,
    ) -> RateRiskReadModel:
        read_model = super().build_from_analysis(request=request, result=result)
        failures = result.source_load.snapshot.mapping_failures
        failure_rows = tuple(
            RateRiskSourceMappingFailureRow(
                source_record_id=item.source_record_id,
                source_reference=item.source_reference,
                code=item.code.value,
                canonical_field=item.canonical_field,
                message=item.message,
            )
            for item in sorted(
                failures,
                key=lambda value: (value.source_record_id, value.code.value),
            )
        )
        source_summary_rows = cls._source_summary_rows(result)
        readiness = replace(
            read_model.readiness,
            source_mapping_failure_count=len(failure_rows),
        )
        warnings = list(read_model.warnings)
        if failure_rows:
            warnings.append(
                f"{len(failure_rows)} registro(s) de fuente no pudieron normalizarse al contrato RTILB. "
                "Revise Calidad de Datos."
            )

        return replace(
            read_model,
            readiness=readiness,
            source_summary_rows=source_summary_rows,
            source_mapping_failure_rows=failure_rows,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    @classmethod
    def _source_summary_rows(
        cls,
        result: IRRBBAnalysisResult,
    ) -> tuple[RateRiskSourceSummaryRow, ...]:
        assessments = {
            assessment.position_id: assessment.status.value
            for assessment in result.source_load.assessments
        }
        grouped = defaultdict(list)
        for record in result.source_load.snapshot.position_records:
            grouped[record.position.instrument_class].append(record.position)

        rows: list[RateRiskSourceSummaryRow] = []
        for segment, positions in sorted(
            grouped.items(),
            key=lambda item: cls._SEGMENT_ORDER.get(item[0], 99),
        ):
            statuses = Counter(assessments.get(position.position_id, "") for position in positions)
            rows.append(
                RateRiskSourceSummaryRow(
                    segment=segment.value,
                    label=cls._SEGMENT_LABELS.get(segment, segment.value),
                    position_count=len(positions),
                    ready_count=statuses["READY"],
                    incomplete_count=statuses["INCOMPLETE"],
                    excluded_count=statuses["EXCLUDED"],
                    currencies=tuple(sorted({position.currency.value for position in positions})),
                )
            )
        return tuple(rows)
