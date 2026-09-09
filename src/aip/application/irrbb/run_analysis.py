from __future__ import annotations

from collections import defaultdict
from datetime import date

from aip.application.irrbb.analysis_contracts import (
    IRRBBAnalysisRequest,
    IRRBBAnalysisResult,
    IRRBBAnalysisStatus,
    IRRBBGapCoverageIssue,
    IRRBBGapCoverageIssueCode,
    IRRBBGapCurrencyResult,
    IRRBBGapMatrixCell,
)
from aip.application.irrbb.contracts import (
    IRRBBPositionSourceRecord,
    IRRBBSourceLoadRequest,
    IRRBBSourceLoadResult,
    IRRBBSourceLoadStatus,
)
from aip.application.irrbb.load_source import LoadIRRBBSourceSnapshot
from aip.domain.irrbb.ports import TierOneCapitalProvider
from aip.domain.irrbb.services.scenario_evaluation_service import (
    IRRBBScenarioEvaluationService,
)
from aip.domain.irrbb.services.sugef_gap_row_classifier_service import (
    SugefGapRowClassifierService,
)
from aip.domain.irrbb.services.sugef_standard_gap_service import SugefStandardGapService
from aip.domain.irrbb.sugef_standard_gap import (
    SugefGapExposure,
    SugefGapReportLine,
    SugefGapRowClassification,
    SugefGapRowClassificationStatus,
)
from aip.shared.money import Currency


class RunIRRBBAnalysis:
    """Compose validated source data with certified RTILB domain services.

    EVE/Delta EVE uses only positions declared READY by Phase 5. SUGEF GAP is
    calculated independently, in each native currency, and missing/invalid GAP
    schedules are surfaced as coverage issues rather than treated as zero exposure.
    """

    def __init__(
        self,
        *,
        source_loader: LoadIRRBBSourceSnapshot,
        scenario_evaluation: IRRBBScenarioEvaluationService,
        tier_one_capital: TierOneCapitalProvider,
    ) -> None:
        self._source_loader = source_loader
        self._scenario_evaluation = scenario_evaluation
        self._tier_one_capital = tier_one_capital

    def execute(self, request: IRRBBAnalysisRequest) -> IRRBBAnalysisResult:
        source_load = self._source_loader.execute(IRRBBSourceLoadRequest(request.cutoff_date))
        classifications = self._classify_gap_rows(source_load)

        if source_load.status is IRRBBSourceLoadStatus.EMPTY:
            return self._uncalculated_result(
                status=IRRBBAnalysisStatus.NO_DATA,
                source_load=source_load,
                classifications=classifications,
            )

        ready_records = self._ready_records(source_load)
        if not ready_records:
            return self._uncalculated_result(
                status=IRRBBAnalysisStatus.BLOCKED,
                source_load=source_load,
                classifications=classifications,
            )

        tier_one_capital = self._tier_one_capital.tier_one_capital(
            cutoff_date=request.cutoff_date,
            reporting_currency=request.reporting_currency,
        )
        evaluation = self._scenario_evaluation.evaluate(
            positions=tuple(record.position for record in ready_records),
            valuation_date=request.cutoff_date,
            reporting_currency=request.reporting_currency,
            tier_one_capital=tier_one_capital,
            methodology=request.methodology,
            required_scenarios=request.required_scenarios,
        )
        gap_results, gap_issues = self._calculate_gap(
            ready_records=ready_records,
            classifications=classifications,
            valuation_date=request.cutoff_date,
        )

        has_data_gaps = (
            source_load.status is not IRRBBSourceLoadStatus.READY or bool(gap_issues)
        )
        status = (
            IRRBBAnalysisStatus.CALCULATED_WITH_DATA_GAPS
            if has_data_gaps
            else IRRBBAnalysisStatus.CALCULATED
        )
        return IRRBBAnalysisResult(
            status=status,
            source_load=source_load,
            evaluation=evaluation,
            tier_one_capital=tier_one_capital,
            gap_classifications=classifications,
            gap_results=gap_results,
            gap_issues=gap_issues,
            curve_points=source_load.snapshot.curve_points,
        )

    @staticmethod
    def _ready_records(
        source_load: IRRBBSourceLoadResult,
    ) -> tuple[IRRBBPositionSourceRecord, ...]:
        ready = set(source_load.ready_position_ids)
        return tuple(
            record
            for record in source_load.snapshot.position_records
            if record.position.position_id in ready
        )

    @staticmethod
    def _classify_gap_rows(
        source_load: IRRBBSourceLoadResult,
    ) -> tuple[SugefGapRowClassification, ...]:
        return tuple(
            SugefGapRowClassifierService.classify(
                position=record.position,
                routing=record.gap_routing_metadata,
            )
            for record in source_load.snapshot.position_records
        )

    @staticmethod
    def _calculate_gap(
        *,
        ready_records: tuple[IRRBBPositionSourceRecord, ...],
        classifications: tuple[SugefGapRowClassification, ...],
        valuation_date: date,
    ) -> tuple[tuple[IRRBBGapCurrencyResult, ...], tuple[IRRBBGapCoverageIssue, ...]]:
        classification_by_id = {item.position_id: item for item in classifications}
        exposures_by_currency: dict[Currency, list[SugefGapExposure]] = defaultdict(list)
        exposures_by_line: dict[
            tuple[Currency, SugefGapReportLine], list[SugefGapExposure]
        ] = defaultdict(list)
        positions_by_currency: dict[Currency, set[str]] = defaultdict(set)
        issues: list[IRRBBGapCoverageIssue] = []

        for record in ready_records:
            position = record.position
            classification = classification_by_id[position.position_id]
            if classification.status is not SugefGapRowClassificationStatus.MAPPED:
                issues.append(
                    IRRBBGapCoverageIssue(
                        position_id=position.position_id,
                        code=IRRBBGapCoverageIssueCode.ROW_NOT_MAPPED,
                        message=classification.reason,
                    )
                )
                continue

            if not record.gap_schedule:
                issues.append(
                    IRRBBGapCoverageIssue(
                        position_id=position.position_id,
                        code=IRRBBGapCoverageIssueCode.SCHEDULE_MISSING,
                        message=(
                            "Position is calculation-ready for EVE but has no explicit "
                            "SUGEF GAP schedule. No zero exposure was assumed."
                        ),
                    )
                )
                continue

            try:
                exposures = SugefStandardGapService.build_exposures(
                    position=position,
                    schedule=record.gap_schedule,
                    valuation_date=valuation_date,
                )
            except ValueError as exc:
                issues.append(
                    IRRBBGapCoverageIssue(
                        position_id=position.position_id,
                        code=IRRBBGapCoverageIssueCode.SCHEDULE_INVALID,
                        message=str(exc),
                    )
                )
                continue

            report_line = classification.report_line
            if report_line is None:
                raise RuntimeError("mapped SUGEF GAP classification has no report line")
            exposures_by_currency[position.currency].extend(exposures)
            exposures_by_line[(position.currency, report_line)].extend(exposures)
            positions_by_currency[position.currency].add(position.position_id)

        results: list[IRRBBGapCurrencyResult] = []
        for currency in sorted(exposures_by_currency, key=lambda item: item.value):
            bucket_totals = SugefStandardGapService.aggregate_by_bucket(
                exposures=tuple(exposures_by_currency[currency]),
                valuation_date=valuation_date,
            )
            matrix_cells: list[IRRBBGapMatrixCell] = []
            lines = sorted(
                (
                    line
                    for line_currency, line in exposures_by_line
                    if line_currency is currency
                ),
                key=lambda item: item.value,
            )
            for report_line in lines:
                line_totals = SugefStandardGapService.aggregate_by_bucket(
                    exposures=tuple(exposures_by_line[(currency, report_line)]),
                    valuation_date=valuation_date,
                )
                matrix_cells.extend(
                    IRRBBGapMatrixCell(
                        report_line=report_line,
                        bucket=total.bucket,
                        ordinal=total.ordinal,
                        bucket_label=total.label,
                        amount=total.amount,
                    )
                    for total in line_totals
                )

            results.append(
                IRRBBGapCurrencyResult(
                    currency=currency,
                    bucket_totals=bucket_totals,
                    matrix_cells=tuple(matrix_cells),
                    included_position_ids=tuple(sorted(positions_by_currency[currency])),
                )
            )

        return (tuple(results), tuple(issues))

    @staticmethod
    def _uncalculated_result(
        *,
        status: IRRBBAnalysisStatus,
        source_load: IRRBBSourceLoadResult,
        classifications: tuple[SugefGapRowClassification, ...],
    ) -> IRRBBAnalysisResult:
        return IRRBBAnalysisResult(
            status=status,
            source_load=source_load,
            evaluation=None,
            tier_one_capital=None,
            gap_classifications=classifications,
            gap_results=(),
            gap_issues=(),
            curve_points=source_load.snapshot.curve_points,
        )
