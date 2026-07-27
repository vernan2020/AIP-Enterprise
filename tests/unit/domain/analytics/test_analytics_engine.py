from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from aip.domain.analytics.enums.normalization_method import NormalizationMethod
from aip.domain.analytics.enums.outlier_method import OutlierMethod
from aip.domain.analytics.enums.ranking_order import RankingOrder
from aip.domain.analytics.enums.score_direction import ScoreDirection
from aip.domain.analytics.exceptions import (
    AnalyticsError,
    DuplicateRankItemError,
    ExplainabilityError,
    InvalidScoreBandError,
    InvalidWeightError,
    NormalizationError,
    RankingError,
    ScoringError,
    StatisticsError,
)
from aip.domain.analytics.explainability.explanation_builder import ExplanationBuilder
from aip.domain.analytics.explainability.explanation_factor import ExplanationFactor
from aip.domain.analytics.models.analytics_context import AnalyticsContext
from aip.domain.analytics.models.metric_observation import MetricObservation
from aip.domain.analytics.normalization.min_max import MinMaxNormalizer
from aip.domain.analytics.normalization.percentile_rank import PercentileRank
from aip.domain.analytics.normalization.robust_scaler import RobustScaler
from aip.domain.analytics.normalization.z_score import ZScoreNormalizer
from aip.domain.analytics.ranking.rank_item import RankItem
from aip.domain.analytics.ranking.ranking_engine import RankingEngine
from aip.domain.analytics.ranking.tie_breaker import TieBreaker
from aip.domain.analytics.scoring.composite_score import CompositeScore
from aip.domain.analytics.scoring.score_band import ScoreBand
from aip.domain.analytics.scoring.score_component import ScoreComponent
from aip.domain.analytics.scoring.weighted_score import WeightedScore
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics
from aip.domain.analytics.statistics.outlier_detection import OutlierDetection
from aip.domain.analytics.statistics.weighted_statistics import WeightedStatistics


def test_metric_observation_validation_and_metadata_copying() -> None:
    observation = MetricObservation(
        metric_name="score",
        value=Decimal("12.34"),
        unit="bps",
        source="feed",
        timestamp=datetime(2026, 7, 27, 9, 0, 0),
        metadata={"region": "EMEA"},
    )
    assert observation.value == Decimal("12.34")
    assert observation.metadata == {"region": "EMEA"}
    observation.metadata["region"] = "APAC"
    assert observation.metadata == {"region": "APAC"}
    with pytest.raises(AnalyticsError):
        MetricObservation(metric_name="", value=Decimal("1"))
    with pytest.raises(AnalyticsError):
        MetricObservation(metric_name="bad", value=Decimal("NaN"))
    with pytest.raises(AnalyticsError):
        MetricObservation(metric_name="bad", value=Decimal("Infinity"))


def test_normalizers_cover_constant_empty_and_single_value_series() -> None:
    min_max = MinMaxNormalizer(lower=Decimal("0"), upper=Decimal("100"))
    assert min_max.normalize([Decimal("1"), Decimal("3")]) == [Decimal("0"), Decimal("100")]
    with pytest.raises(NormalizationError):
        min_max.normalize([])
    assert min_max.normalize([Decimal("2"), Decimal("2")]) == [Decimal("0"), Decimal("0")]
    with pytest.raises(NormalizationError):
        MinMaxNormalizer(lower=Decimal("1"), upper=Decimal("1"))

    z_score = ZScoreNormalizer()
    with pytest.raises(NormalizationError):
        z_score.normalize([Decimal("1"), Decimal("1")])
    assert z_score.normalize([Decimal("5")]) == [Decimal("0")]

    robust = RobustScaler()
    with pytest.raises(NormalizationError):
        robust.normalize([Decimal("2"), Decimal("2")])
    with pytest.raises(NormalizationError):
        robust.normalize([])
    assert robust.normalize([Decimal("5")]) == [Decimal("0")]

    percentile = PercentileRank()
    assert percentile.normalize([Decimal("10"), Decimal("20"), Decimal("30")]) == [Decimal("0.3333333333333333333333333333"), Decimal("0.6666666666666666666666666667"), Decimal("1")]


def test_score_component_and_weighted_score_validation() -> None:
    component = ScoreComponent(
        component_name="credit",
        raw_value=Decimal("3"),
        normalized_value=Decimal("0.8"),
        weight=Decimal("0.5"),
        score_direction=ScoreDirection.HIGHER_IS_BETTER,
        contribution=Decimal("0.4"),
        minimum_threshold=Decimal("0"),
        maximum_threshold=Decimal("1"),
    )
    assert component.normalized_value == Decimal("0.8")
    with pytest.raises(ScoringError):
        ScoreComponent(component_name="", raw_value=Decimal("1"), normalized_value=Decimal("0.2"), weight=Decimal("1"), score_direction=ScoreDirection.HIGHER_IS_BETTER, contribution=Decimal("0.2"))
    with pytest.raises(ScoringError):
        ScoreComponent(component_name="bad", raw_value=Decimal("1"), normalized_value=Decimal("2"), weight=Decimal("1"), score_direction=ScoreDirection.HIGHER_IS_BETTER, contribution=Decimal("0.2"))
    with pytest.raises(ScoringError):
        ScoreComponent(component_name="bad", raw_value=Decimal("1"), normalized_value=Decimal("0.2"), weight=Decimal("-1"), score_direction=ScoreDirection.HIGHER_IS_BETTER, contribution=Decimal("0.2"))
    with pytest.raises(ScoringError):
        ScoreComponent(component_name="bad", raw_value=Decimal("1"), normalized_value=Decimal("0.2"), weight=Decimal("1"), score_direction=ScoreDirection.TARGET_IS_BEST, contribution=Decimal("0.2"))
    with pytest.raises(ScoringError):
        ScoreComponent(component_name="bad", raw_value=Decimal("1"), normalized_value=Decimal("0.2"), weight=Decimal("1"), score_direction=ScoreDirection.HIGHER_IS_BETTER, contribution=Decimal("0.2"), minimum_threshold=Decimal("1"), maximum_threshold=Decimal("0"))

    with pytest.raises(InvalidWeightError):
        WeightedScore(final_score=Decimal("0"), total_effective_weight=Decimal("0"), component_contributions=())


def test_target_is_best_and_composite_scoring() -> None:
    component = ScoreComponent(
        component_name="liquidity",
        raw_value=Decimal("1"),
        normalized_value=Decimal("0.9"),
        weight=Decimal("2"),
        score_direction=ScoreDirection.TARGET_IS_BEST,
        contribution=Decimal("1.8"),
        target_value=Decimal("1"),
    )
    assert component.score_direction is ScoreDirection.TARGET_IS_BEST

    bands = (
        ScoreBand(code="VL", label="VERY_LOW", minimum=Decimal("0"), maximum=Decimal("0.25")),
        ScoreBand(code="LH", label="LOW", minimum=Decimal("0.25"), maximum=Decimal("0.5"), inclusive_minimum=False),
        ScoreBand(code="MD", label="MEDIUM", minimum=Decimal("0.5"), maximum=Decimal("0.75"), inclusive_minimum=False),
        ScoreBand(code="HG", label="HIGH", minimum=Decimal("0.75"), maximum=Decimal("1"), inclusive_minimum=False),
    )
    composite = CompositeScore(final_score=Decimal("0.8"), score_scale=(Decimal("0"), Decimal("1")), score_bands=bands, weighted_scores=())
    assert composite.determine_band(Decimal("0.8")).code == "HG"
    with pytest.raises(InvalidScoreBandError):
        composite.determine_band(Decimal("1.2"))


def test_ranking_engine_ties_and_deterministic_ordering() -> None:
    engine = RankingEngine()
    items = [
        RankItem(business_id="B", primary_score=Decimal("10")),
        RankItem(business_id="A", primary_score=Decimal("10")),
        RankItem(business_id="C", primary_score=Decimal("8")),
    ]
    result = engine.rank(items, RankingOrder.DESCENDING)
    assert result.ranked_items[0].business_id == "B"
    assert result.ordinal_rank == (1, 2, 3)
    assert result.dense_rank == (1, 1, 2)
    assert result.percentile_rank[0] == Decimal("0.3333333333333333333333333333")
    with pytest.raises(DuplicateRankItemError):
        engine.rank([RankItem(business_id="A", primary_score=Decimal("1")), RankItem(business_id="A", primary_score=Decimal("2"))], RankingOrder.DESCENDING)
    with pytest.raises(RankingError):
        engine.rank([], RankingOrder.DESCENDING)

    tie_breaker = TieBreaker(metric_name="volatility", business_id_first=False, ranking_order=RankingOrder.ASCENDING)
    ranked = engine.rank(
        [
            RankItem(business_id="C", primary_score=Decimal("10"), secondary_metrics=(("volatility", Decimal("2")),)),
            RankItem(business_id="A", primary_score=Decimal("10"), secondary_metrics=(("volatility", Decimal("1")),)),
        ],
        RankingOrder.DESCENDING,
        tie_breaker=tie_breaker,
    )
    assert ranked.ranked_items[0].business_id == "A"

    ascending_result = engine.rank(
        [RankItem(business_id="A", primary_score=Decimal("10")), RankItem(business_id="B", primary_score=Decimal("5"))],
        RankingOrder.ASCENDING,
    )
    assert ascending_result.ranked_items[0].business_id == "B"


def test_descriptive_and_weighted_statistics() -> None:
    stats = DescriptiveStatistics([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")], sample=True)
    assert stats.count() == 4
    assert stats.sum() == Decimal("10")
    assert stats.mean() == Decimal("2.5")
    assert stats.median() == Decimal("2.5")
    assert stats.minimum() == Decimal("1")
    assert stats.maximum() == Decimal("4")
    assert stats.variance() == Decimal("1.6666666666666666666666666667") or stats.variance() == Decimal("1.666666666666666666666666667")
    assert stats.percentile(Decimal("0.5")) == Decimal("2.5")
    assert stats.coefficient_of_variation() == Decimal("0.5163977794943222513572353868")
    assert stats.interquartile_range() == Decimal("1.5")
    weighted = WeightedStatistics([Decimal("1"), Decimal("2"), Decimal("3")], [Decimal("1"), Decimal("1"), Decimal("2")])
    assert weighted.weighted_mean() == Decimal("2.25")
    assert weighted.weighted_variance() > 0
    with pytest.raises(StatisticsError):
        WeightedStatistics([Decimal("1")], [Decimal("0")])
    with pytest.raises(StatisticsError):
        WeightedStatistics([Decimal("1"), Decimal("2")], [Decimal("1")])
    with pytest.raises(StatisticsError):
        DescriptiveStatistics([])
    with pytest.raises(StatisticsError):
        DescriptiveStatistics([Decimal("NaN")])


def test_normalization_edge_cases_and_tie_behaviors() -> None:
    min_max = MinMaxNormalizer(lower=Decimal("0"), upper=Decimal("1"))
    with pytest.raises(NormalizationError):
        min_max.normalize([Decimal("NaN")])
    with pytest.raises(NormalizationError):
        ZScoreNormalizer().normalize([Decimal("NaN")])
    with pytest.raises(NormalizationError):
        RobustScaler().normalize([Decimal("NaN")])

    percentile = PercentileRank(tie_method="max")
    assert percentile.normalize([Decimal("1"), Decimal("1"), Decimal("2")])[0] == Decimal("0.6666666666666666666666666667")
    assert percentile.normalize([Decimal("2")])[0] == Decimal("1")

    single = DescriptiveStatistics([Decimal("7")])
    assert single.quartiles() == (Decimal("7"), Decimal("7"), Decimal("7"))
    assert single.percentile(Decimal("0.5")) == Decimal("7")


def test_outlier_detection_methods_and_explanation_builder() -> None:
    iqr_detector = OutlierDetection(OutlierMethod.IQR)
    result = iqr_detector.detect([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("100")])
    assert result.outliers == (Decimal("100"),)
    z_detector = OutlierDetection(OutlierMethod.Z_SCORE)
    assert z_detector.detect([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("100")]).outliers == (Decimal("100"),)
    modified = OutlierDetection(OutlierMethod.MODIFIED_Z_SCORE)
    assert modified.detect([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("100")]).outliers == (Decimal("100"),)

    builder = ExplanationBuilder()
    explanation = builder.build(
        concise_conclusion="Score is strong",
        factors=[ExplanationFactor(name="value", value=Decimal("0.8"), direction="up", contribution=Decimal("0.2"))],
    )
    assert explanation.concise_conclusion == "Score is strong"
    assert explanation.supporting_factors[0].name == "value"
    with pytest.raises(ExplainabilityError):
        builder.build(concise_conclusion="", factors=[])


def test_weighted_statistics_and_tie_breaker_edge_cases() -> None:
    with pytest.raises(StatisticsError):
        WeightedStatistics([Decimal("1")], [Decimal("-1")])
    with pytest.raises(StatisticsError):
        WeightedStatistics([Decimal("1"), Decimal("2")], [Decimal("1")])

    tie_breaker = TieBreaker(metric_name="volatility")
    assert tie_breaker.resolve(RankItem(business_id="A", primary_score=Decimal("1")), RankItem(business_id="B", primary_score=Decimal("1"))) == -1
    assert TieBreaker().resolve(RankItem(business_id="A", primary_score=Decimal("1")), RankItem(business_id="B", primary_score=Decimal("1"))) == -1


def test_context_and_exceptions() -> None:
    context = AnalyticsContext(
        valuation_date="2026-07-27",
        base_currency="USD",
        market_snapshot_reference="snapshot-1",
        portfolio_reference="portfolio-1",
        configuration_version="v1",
        calculation_timestamp=datetime(2026, 7, 27, 9, 0, 0),
        calculation_identifier="calc-1",
        user_or_process_reference="process-1",
    )
    assert context.base_currency == "USD"
    with pytest.raises(InvalidScoreBandError):
        ScoreBand(code="A", label="Bad", minimum=Decimal("1"), maximum=Decimal("0"))
