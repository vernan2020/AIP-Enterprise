from datetime import date
from decimal import Decimal

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.readers.sugef_financial_api_client import SUGEFApiReadResult
from aip.product.configured.readers.sugef_financial_statement_reader import (
    SUGEFFinancialReadResult,
)
from aip.product.configured.services.configured_financial_analysis_service import (
    ConfiguredFinancialAnalysisService,
)


def test_atlas_comparison_skips_full_refresh_and_preserves_history():
    cutoff = date(2026, 9, 30)
    calls = []

    class FullReader:
        def read(self, *, cutoff_date):
            raise AssertionError("Atlas must not refresh the full financial universe")

    class EmptyFullReader:
        def read(self, *, cutoff_date):
            return SUGEFFinancialReadResult((), (), (), "TEST")

        def fingerprint(self, *, cutoff_date):
            return "TEST"

    class HistoryReader:
        def read_entity_history_range(self, entity_id, cutoff_date, *, lookback_months):
            calls.append((entity_id, cutoff_date, lookback_months))
            entity = FinancialEntity(entity_id, "Entidad " + entity_id)
            lines = tuple(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=period,
                    statement_type=FinancialStatementType.BALANCE_SHEET,
                    account_code="10000",
                    account_name="ACTIVO TOTAL",
                    amount=Decimal(amount),
                )
                for period, amount in (
                    (date(2026, 8, 31), "100000000"),
                    (cutoff, "110000000"),
                )
            )
            return SUGEFApiReadResult(lines, ("SUGEF-HISTORY",), ())

    def make_service(reader, history_only):
        return ConfiguredFinancialAnalysisService(
            SUGEFFinancialSourceConfig(),
            ValuationDateContext(cutoff),
            reader=reader,
            history_reader=HistoryReader(),
            comparison_history_only=history_only,
        )

    atlas = make_service(FullReader(), True)
    result = atlas.load_comparison(entity_ids=("A", "B"), cutoff_date=cutoff, lookback_months=23)
    assert {item[0] for item in calls} == {"A", "B"}
    assert all(item[2] == 23 for item in calls)
    assert len(calls) == 2
    atlas.load_comparison(entity_ids=("A", "B"), cutoff_date=cutoff, lookback_months=23)
    assert len(calls) == 2
    baseline = make_service(EmptyFullReader(), False).load_comparison(
        entity_ids=("A", "B"), cutoff_date=cutoff, lookback_months=23
    )
    assert [item.metric_history for item in result] == [item.metric_history for item in baseline]
    assert [item.selected_entity.entity_id for item in result] == ["A", "B"]
    assets = next(series for series in result[0].metric_history if series.code == "ASSETS")
    assert assets.points[-1].value == Decimal("110000000")
    assert result[0].source_files == ("SUGEF-HISTORY",)
