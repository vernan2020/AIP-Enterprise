from __future__ import annotations

from dataclasses import replace

from aip.application.irrbb import IRRBBAnalysisRequest, IRRBBAnalysisResult
from aip.ui.modules.rate_risk.models import (
    RateRiskReadModel,
    RateRiskSourceMappingFailureRow,
)
from aip.ui.modules.rate_risk.presenters.rate_risk_presenter import (
    RateRiskPresenter as _BaseRateRiskPresenter,
)


class RateRiskPresenter(_BaseRateRiskPresenter):
    """Extend the certified RTILB presenter with pre-canonical source diagnostics.

    The base presenter remains responsible for financial and canonical data-quality
    presentation. This extension only exposes mapping failures already produced by
    the source anti-corruption layer; it performs no source inference or financial
    calculation.
    """

    @classmethod
    def build_from_analysis(
        cls,
        *,
        request: IRRBBAnalysisRequest,
        result: IRRBBAnalysisResult,
    ) -> RateRiskReadModel:
        read_model = super().build_from_analysis(request=request, result=result)
        failures = result.source_load.snapshot.mapping_failures
        rows = tuple(
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
        readiness = replace(
            read_model.readiness,
            source_mapping_failure_count=len(rows),
        )
        warnings = list(read_model.warnings)
        if rows:
            warnings.append(
                f"{len(rows)} registro(s) de fuente no pudieron normalizarse al contrato RTILB. "
                "Revise Calidad de Datos."
            )

        return replace(
            read_model,
            readiness=readiness,
            source_mapping_failure_rows=rows,
            warnings=tuple(dict.fromkeys(warnings)),
        )
