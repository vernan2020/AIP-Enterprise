from __future__ import annotations

from collections import Counter
from dataclasses import replace
from decimal import Decimal

from aip.application.irrbb import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisResult,
    IRRBBAnalysisStatus,
)
from aip.domain.irrbb.data_quality import (
    IRRBBDataQualitySeverity,
    IRRBBDataQualityStatus,
    IRRBBPositionAssessment,
)
from aip.domain.irrbb.models import IRRBBScenario
from aip.domain.irrbb.scenario_evaluation import IRRBBScenarioEvaluationResult
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapBucketTotal,
    SugefGapReportLine,
    SugefGapRowClassification,
    SugefGapRowClassificationStatus,
)
from aip.ui.modules.rate_risk.models.rate_risk_read_model import (
    RateRiskCurvePointInput,
    RateRiskCurvePointRow,
    RateRiskDataIssueRow,
    RateRiskGapBucketRow,
    RateRiskGapCoverageIssueRow,
    RateRiskGapMatrixCellInput,
    RateRiskGapMatrixCellRow,
    RateRiskKpi,
    RateRiskMappingRow,
    RateRiskMethodologyMetadata,
    RateRiskPositionQualityRow,
    RateRiskReadinessSummary,
    RateRiskReadModel,
    RateRiskScenarioRow,
    RateRiskValuationFlowRow,
)


class RateRiskPresenter:
    """Transform certified IRRBB outputs into a passive UI read model.

    No discounting, repricing, GAP aggregation, curve construction or behavioral
    modeling is performed here. This class only validates consistency, labels
    already-computed results and arranges them for a PySide6 view.
    """

    _SCENARIO_LABELS = {
        IRRBBScenario.BASE: "Base",
        IRRBBScenario.PARALLEL_UP: "Paralelo +",
        IRRBBScenario.PARALLEL_DOWN: "Paralelo -",
        IRRBBScenario.STEEPENER: "Empinamiento",
        IRRBBScenario.FLATTENER: "Aplanamiento",
        IRRBBScenario.SHORT_UP: "Corto +",
        IRRBBScenario.SHORT_DOWN: "Corto -",
    }

    _REPORT_LINE_LABELS = {
        SugefGapReportLine.INVESTMENT_FIXED: "Inversiones · tasa fija",
        SugefGapReportLine.INVESTMENT_VARIABLE_SEMIVARIABLE: (
            "Inversiones · tasa variable/semivariable"
        ),
        SugefGapReportLine.CREDIT_FIXED: "Crédito · tasa fija",
        SugefGapReportLine.CREDIT_VARIABLE_SEMIVARIABLE: (
            "Crédito · tasa variable/semivariable"
        ),
        SugefGapReportLine.PUBLIC_SIGHT_WITH_COST: "Público · vista con costo",
        SugefGapReportLine.PUBLIC_SIGHT_WITHOUT_COST: "Público · vista sin costo",
        SugefGapReportLine.PUBLIC_TERM_FIXED: "Público · plazo fijo",
        SugefGapReportLine.PUBLIC_TERM_VARIABLE_SEMIVARIABLE: (
            "Público · plazo variable/semivariable"
        ),
        SugefGapReportLine.BCCR_SIGHT_WITH_COST: "BCCR · vista con costo",
        SugefGapReportLine.BCCR_SIGHT_WITHOUT_COST: "BCCR · vista sin costo",
        SugefGapReportLine.BCCR_TERM_FIXED: "BCCR · plazo fijo",
        SugefGapReportLine.BCCR_TERM_VARIABLE_SEMIVARIABLE: (
            "BCCR · plazo variable/semivariable"
        ),
        SugefGapReportLine.FINANCIAL_ENTITY_SIGHT_WITH_COST: (
            "Entidad financiera · vista con costo"
        ),
        SugefGapReportLine.FINANCIAL_ENTITY_SIGHT_WITHOUT_COST: (
            "Entidad financiera · vista sin costo"
        ),
        SugefGapReportLine.FINANCIAL_ENTITY_TERM_FIXED: (
            "Entidad financiera · plazo fijo"
        ),
        SugefGapReportLine.FINANCIAL_ENTITY_TERM_VARIABLE_SEMIVARIABLE: (
            "Entidad financiera · plazo variable/semivariable"
        ),
    }

    @classmethod
    def build_from_analysis(
        cls,
        *,
        request: IRRBBAnalysisRequest,
        result: IRRBBAnalysisResult,
    ) -> RateRiskReadModel:
        """Present one complete application result without manufacturing values.

        ``NO_DATA`` and ``BLOCKED`` produce an explicit read model with empty KPI,
        scenario, GAP and valuation-flow collections. The view can therefore show
        N/D while still exposing cutoff, methodology, source quality and mappings.
        """

        cls._validate_analysis_context(request=request, result=result)
        curve_points = tuple(
            RateRiskCurvePointInput(
                curve_id=item.curve_id,
                as_of_date=item.as_of_date,
                currency=item.currency,
                scenario=item.scenario,
                tenor_years=item.tenor_years,
                rate=item.rate,
                source_reference=item.source_reference,
            )
            for item in result.curve_points
        )
        gap_issue_rows = tuple(
            RateRiskGapCoverageIssueRow(
                position_id=item.position_id,
                code=item.code.value,
                message=item.message,
            )
            for item in result.gap_issues
        )

        if result.evaluation is None:
            if result.status not in {
                IRRBBAnalysisStatus.NO_DATA,
                IRRBBAnalysisStatus.BLOCKED,
            }:
                raise ValueError(
                    "calculated IRRBB application status requires an evaluation result"
                )
            return cls._build_uncalculated(
                request=request,
                result=result,
                curve_points=curve_points,
                gap_issue_rows=gap_issue_rows,
            )

        if result.status not in {
            IRRBBAnalysisStatus.CALCULATED,
            IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS,
        }:
            raise ValueError("uncalculated IRRBB application status cannot contain evaluation")

        gap_bucket_totals = tuple(
            total
            for currency_result in result.gap_results
            for total in currency_result.bucket_totals
        )
        gap_matrix_cells = tuple(
            RateRiskGapMatrixCellInput(
                report_line=cell.report_line,
                bucket=cell.bucket,
                ordinal=cell.ordinal,
                bucket_label=cell.bucket_label,
                amount=cell.amount,
            )
            for currency_result in result.gap_results
            for cell in currency_result.matrix_cells
        )
        read_model = cls.build(
            evaluation=result.evaluation,
            gap_bucket_totals=gap_bucket_totals,
            gap_matrix_cells=gap_matrix_cells,
            quality_assessments=result.source_load.assessments,
            gap_classifications=result.gap_classifications,
            curve_points=curve_points,
        )

        warnings = list(read_model.warnings)
        if result.status is IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS:
            warnings.insert(
                0,
                "Cálculo RTILB completado con brechas de datos. Revise Calidad de Datos y GAP SUGEF.",
            )
        if gap_issue_rows:
            warnings.append(
                f"{len(gap_issue_rows)} posición(es) listas para VEP no tienen cobertura GAP SUGEF completa."
            )

        return replace(
            read_model,
            analysis_status=result.status.value,
            gap_coverage_issue_rows=gap_issue_rows,
            warnings=cls._deduplicate(warnings),
        )

    @classmethod
    def build(
        cls,
        *,
        evaluation: IRRBBScenarioEvaluationResult,
        gap_bucket_totals: tuple[SugefGapBucketTotal, ...] = (),
        gap_matrix_cells: tuple[RateRiskGapMatrixCellInput, ...] = (),
        quality_assessments: tuple[IRRBBPositionAssessment, ...] = (),
        gap_classifications: tuple[SugefGapRowClassification, ...] = (),
        curve_points: tuple[RateRiskCurvePointInput, ...] = (),
    ) -> RateRiskReadModel:
        assessment_by_scenario = {
            assessment.scenario: assessment
            for assessment in evaluation.exposure.assessments
        }
        stressed_by_scenario = {
            result.scenario: result for result in evaluation.stressed
        }

        if len(assessment_by_scenario) != len(evaluation.exposure.assessments):
            raise ValueError("duplicate scenario assessments cannot be presented")
        if set(stressed_by_scenario) != set(assessment_by_scenario):
            raise ValueError(
                "stressed EVE scenarios and Delta EVE assessments must have identical coverage"
            )

        methodology = RateRiskMethodologyMetadata(
            code=evaluation.methodology.code,
            version=evaluation.methodology.version,
            status=evaluation.methodology.status.value,
            source_reference=evaluation.methodology.source_reference,
            effective_from=evaluation.methodology.effective_from,
            valuation_date=evaluation.valuation_date,
            reporting_currency=evaluation.reporting_currency.value,
            calculated_position_count=evaluation.position_count,
        )

        scenario_rows = [
            RateRiskScenarioRow(
                scenario=IRRBBScenario.BASE.value,
                label=cls._scenario_label(IRRBBScenario.BASE),
                eve=evaluation.base.eve.amount,
                delta_eve=Decimal("0"),
                fall_from_base=Decimal("0"),
                pv_assets=evaluation.base.pv_assets.amount,
                pv_liabilities=evaluation.base.pv_liabilities.amount,
                pv_off_balance_net=evaluation.base.pv_off_balance_net.amount,
                currency=evaluation.reporting_currency.value,
                is_worst=False,
            )
        ]
        for result in evaluation.stressed:
            assessment = assessment_by_scenario[result.scenario]
            scenario_rows.append(
                RateRiskScenarioRow(
                    scenario=result.scenario.value,
                    label=cls._scenario_label(result.scenario),
                    eve=result.eve.amount,
                    delta_eve=assessment.delta_eve.amount,
                    fall_from_base=assessment.fall_from_base.amount,
                    pv_assets=result.pv_assets.amount,
                    pv_liabilities=result.pv_liabilities.amount,
                    pv_off_balance_net=result.pv_off_balance_net.amount,
                    currency=evaluation.reporting_currency.value,
                    is_worst=result.scenario is evaluation.exposure.worst_scenario,
                )
            )

        kpis = (
            RateRiskKpi(
                key="BASE_EVE",
                label="VEP base",
                value=evaluation.base.eve.amount,
                unit="MONEY",
                currency=evaluation.reporting_currency.value,
            ),
            RateRiskKpi(
                key="WORST_EVE_LOSS",
                label="Peor pérdida ΔVEP",
                value=evaluation.exposure.worst_loss.amount,
                unit="MONEY",
                currency=evaluation.reporting_currency.value,
                scenario=evaluation.exposure.worst_scenario.value,
                status="RISK",
            ),
            RateRiskKpi(
                key="EVE_TIER1_RATIO",
                label="ΔVEP / CN1",
                value=evaluation.exposure.exposure_ratio_to_tier1,
                unit="RATIO",
                scenario=evaluation.exposure.worst_scenario.value,
                status="RISK",
            ),
            RateRiskKpi(
                key="TIER1_CAPITAL",
                label="Capital Nivel 1",
                value=evaluation.exposure.tier_one_capital.amount,
                unit="MONEY",
                currency=evaluation.reporting_currency.value,
            ),
            RateRiskKpi(
                key="CALCULATED_POSITIONS",
                label="Posiciones calculadas",
                value=Decimal(evaluation.position_count),
                unit="COUNT",
            ),
        )

        position_quality_rows = cls._position_quality_rows(quality_assessments)
        data_issue_rows = cls._data_issue_rows(quality_assessments)
        mapping_rows = cls._mapping_rows(gap_classifications)
        readiness = cls._readiness_summary(
            calculated_position_count=evaluation.position_count,
            quality_assessments=quality_assessments,
            gap_classifications=gap_classifications,
            data_issue_count=len(data_issue_rows),
        )

        gap_bucket_rows = tuple(
            RateRiskGapBucketRow(
                bucket=item.bucket.value,
                ordinal=item.ordinal,
                label=item.label,
                amount=item.amount.amount,
                currency=item.amount.currency.value,
            )
            for item in sorted(
                gap_bucket_totals,
                key=lambda value: (value.amount.currency.value, value.ordinal),
            )
        )
        gap_matrix_rows = tuple(
            RateRiskGapMatrixCellRow(
                report_line=item.report_line.value,
                report_line_label=cls._report_line_label(item.report_line),
                bucket=item.bucket.value,
                ordinal=item.ordinal,
                bucket_label=item.bucket_label,
                amount=item.amount.amount,
                currency=item.amount.currency.value,
            )
            for item in sorted(
                gap_matrix_cells,
                key=lambda value: (
                    value.amount.currency.value,
                    value.report_line.value,
                    value.ordinal,
                ),
            )
        )

        valuation_flow_rows = tuple(cls._valuation_flow_rows(evaluation))
        curve_rows = cls._curve_rows(curve_points)

        warnings: list[str] = []
        if not quality_assessments:
            warnings.append("No se suministró evaluación de calidad de datos al read-model.")
        if not gap_matrix_cells:
            warnings.append("La matriz SUGEF por fila y banda aún no fue suministrada.")
        if not curve_points:
            warnings.append("No se suministraron puntos de curva para visualización.")

        return RateRiskReadModel(
            methodology=methodology,
            readiness=readiness,
            kpis=kpis,
            scenario_rows=tuple(scenario_rows),
            gap_bucket_rows=gap_bucket_rows,
            gap_matrix_cells=gap_matrix_rows,
            valuation_flow_rows=valuation_flow_rows,
            position_quality_rows=position_quality_rows,
            data_issue_rows=data_issue_rows,
            mapping_rows=mapping_rows,
            curve_rows=curve_rows,
            warnings=tuple(warnings),
        )

    @classmethod
    def _build_uncalculated(
        cls,
        *,
        request: IRRBBAnalysisRequest,
        result: IRRBBAnalysisResult,
        curve_points: tuple[RateRiskCurvePointInput, ...],
        gap_issue_rows: tuple[RateRiskGapCoverageIssueRow, ...],
    ) -> RateRiskReadModel:
        methodology = RateRiskMethodologyMetadata(
            code=request.methodology.code,
            version=request.methodology.version,
            status=request.methodology.status.value,
            source_reference=request.methodology.source_reference,
            effective_from=request.methodology.effective_from,
            valuation_date=request.cutoff_date,
            reporting_currency=request.reporting_currency.value,
            calculated_position_count=0,
        )
        quality_assessments = result.source_load.assessments
        data_issue_rows = cls._data_issue_rows(quality_assessments)
        readiness = cls._readiness_summary(
            calculated_position_count=0,
            quality_assessments=quality_assessments,
            gap_classifications=result.gap_classifications,
            data_issue_count=len(data_issue_rows),
        )
        warning = (
            "No hay posiciones RTILB disponibles para el corte solicitado."
            if result.status is IRRBBAnalysisStatus.NO_DATA
            else (
                "Cálculo RTILB bloqueado: ninguna posición está lista para VEP/ΔVEP. "
                "Revise Calidad de Datos."
            )
        )
        warnings = [warning]
        if gap_issue_rows:
            warnings.append(
                f"Se registraron {len(gap_issue_rows)} incidencia(s) de cobertura GAP SUGEF."
            )

        return RateRiskReadModel(
            methodology=methodology,
            readiness=readiness,
            kpis=(),
            scenario_rows=(),
            gap_bucket_rows=(),
            gap_matrix_cells=(),
            valuation_flow_rows=(),
            position_quality_rows=cls._position_quality_rows(quality_assessments),
            data_issue_rows=data_issue_rows,
            mapping_rows=cls._mapping_rows(result.gap_classifications),
            curve_rows=cls._curve_rows(curve_points),
            warnings=tuple(warnings),
            analysis_status=result.status.value,
            gap_coverage_issue_rows=gap_issue_rows,
        )

    @staticmethod
    def _validate_analysis_context(
        *,
        request: IRRBBAnalysisRequest,
        result: IRRBBAnalysisResult,
    ) -> None:
        if result.source_load.snapshot.cutoff_date != request.cutoff_date:
            raise ValueError("IRRBB analysis result cutoff does not match presentation request")
        evaluation = result.evaluation
        if evaluation is None:
            return
        if evaluation.valuation_date != request.cutoff_date:
            raise ValueError("IRRBB evaluation cutoff does not match presentation request")
        if evaluation.reporting_currency is not request.reporting_currency:
            raise ValueError(
                "IRRBB evaluation reporting currency does not match presentation request"
            )
        if evaluation.methodology != request.methodology:
            raise ValueError("IRRBB evaluation methodology does not match presentation request")
        if result.tier_one_capital != evaluation.exposure.tier_one_capital:
            raise ValueError("IRRBB Tier 1 capital result is inconsistent with Delta EVE")

    @classmethod
    def _valuation_flow_rows(
        cls,
        evaluation: IRRBBScenarioEvaluationResult,
    ) -> list[RateRiskValuationFlowRow]:
        results = (evaluation.base, *evaluation.stressed)
        rows: list[RateRiskValuationFlowRow] = []
        for result in results:
            for discounted in result.discounted_cashflows:
                flow = discounted.cashflow
                rows.append(
                    RateRiskValuationFlowRow(
                        scenario=result.scenario.value,
                        position_id=flow.position_id,
                        side=flow.side.value,
                        direction=flow.direction.value,
                        flow_type=flow.flow_type,
                        amount_status=flow.amount_status.value,
                        cashflow_date=flow.cashflow_date,
                        risk_date=flow.risk_date,
                        amount=flow.amount.amount,
                        amount_currency=flow.amount.currency.value,
                        discount_factor=discounted.discount_factor,
                        exchange_rate=discounted.exchange_rate,
                        present_value_reporting=discounted.present_value_reporting.amount,
                        signed_eve_contribution=discounted.signed_eve_contribution.amount,
                        reporting_currency=result.reporting_currency.value,
                        source_reference=flow.source_reference,
                        projection_basis=flow.projection_basis,
                    )
                )
        rows.sort(key=lambda item: (item.scenario, item.cashflow_date, item.position_id))
        return rows

    @staticmethod
    def _position_quality_rows(
        assessments: tuple[IRRBBPositionAssessment, ...],
    ) -> tuple[RateRiskPositionQualityRow, ...]:
        rows: list[RateRiskPositionQualityRow] = []
        for assessment in assessments:
            severity_counts = Counter(issue.severity for issue in assessment.issues)
            rows.append(
                RateRiskPositionQualityRow(
                    position_id=assessment.position_id,
                    status=assessment.status.value,
                    issue_count=len(assessment.issues),
                    error_count=severity_counts[IRRBBDataQualitySeverity.ERROR],
                    warning_count=severity_counts[IRRBBDataQualitySeverity.WARNING],
                    info_count=severity_counts[IRRBBDataQualitySeverity.INFO],
                )
            )
        return tuple(sorted(rows, key=lambda item: item.position_id))

    @staticmethod
    def _data_issue_rows(
        assessments: tuple[IRRBBPositionAssessment, ...],
    ) -> tuple[RateRiskDataIssueRow, ...]:
        rows = [
            RateRiskDataIssueRow(
                position_id=assessment.position_id,
                status=assessment.status.value,
                code=issue.code.value,
                field_name=issue.field_name,
                severity=issue.severity.value,
                message=issue.message,
            )
            for assessment in assessments
            for issue in assessment.issues
        ]
        return tuple(
            sorted(
                rows,
                key=lambda item: (
                    item.position_id,
                    item.severity,
                    item.code,
                ),
            )
        )

    @classmethod
    def _mapping_rows(
        cls,
        classifications: tuple[SugefGapRowClassification, ...],
    ) -> tuple[RateRiskMappingRow, ...]:
        return tuple(
            RateRiskMappingRow(
                position_id=item.position_id,
                status=item.status.value,
                report_line=(
                    item.report_line.value if item.report_line is not None else None
                ),
                report_line_label=(
                    cls._report_line_label(item.report_line)
                    if item.report_line is not None
                    else None
                ),
                reason=item.reason,
            )
            for item in classifications
        )

    @staticmethod
    def _readiness_summary(
        *,
        calculated_position_count: int,
        quality_assessments: tuple[IRRBBPositionAssessment, ...],
        gap_classifications: tuple[SugefGapRowClassification, ...],
        data_issue_count: int,
    ) -> RateRiskReadinessSummary:
        quality_counts = Counter(item.status for item in quality_assessments)
        mapping_counts = Counter(item.status for item in gap_classifications)
        return RateRiskReadinessSummary(
            calculated_position_count=calculated_position_count,
            assessed_position_count=len(quality_assessments),
            ready_position_count=quality_counts[IRRBBDataQualityStatus.READY],
            incomplete_position_count=quality_counts[IRRBBDataQualityStatus.INCOMPLETE],
            excluded_position_count=quality_counts[IRRBBDataQualityStatus.EXCLUDED],
            data_issue_count=data_issue_count,
            mapping_pending_count=mapping_counts[
                SugefGapRowClassificationStatus.MAPPING_PENDING
            ],
            incomplete_mapping_count=mapping_counts[
                SugefGapRowClassificationStatus.INCOMPLETE
            ],
        )

    @staticmethod
    def _curve_rows(
        curve_points: tuple[RateRiskCurvePointInput, ...],
    ) -> tuple[RateRiskCurvePointRow, ...]:
        return tuple(
            RateRiskCurvePointRow(
                curve_id=item.curve_id,
                as_of_date=item.as_of_date,
                currency=item.currency.value,
                scenario=item.scenario.value,
                tenor_years=item.tenor_years,
                rate=item.rate,
                source_reference=item.source_reference,
            )
            for item in sorted(
                curve_points,
                key=lambda value: (
                    value.currency.value,
                    value.scenario.value,
                    value.curve_id,
                    value.tenor_years,
                ),
            )
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

    @classmethod
    def _scenario_label(cls, scenario: IRRBBScenario) -> str:
        try:
            return cls._SCENARIO_LABELS[scenario]
        except KeyError as exc:
            raise ValueError(
                f"unsupported IRRBB scenario for presentation: {scenario.value}"
            ) from exc

    @classmethod
    def _report_line_label(cls, line: SugefGapReportLine) -> str:
        try:
            return cls._REPORT_LINE_LABELS[line]
        except KeyError as exc:
            raise ValueError(
                f"unsupported SUGEF report line for presentation: {line.value}"
            ) from exc
