"""Analytics domain package."""

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
from aip.domain.analytics.explainability.explanation import Explanation
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
from aip.domain.analytics.ranking.ranking_result import RankingResult
from aip.domain.analytics.ranking.tie_breaker import TieBreaker
from aip.domain.analytics.scoring.composite_score import CompositeScore
from aip.domain.analytics.scoring.score_band import ScoreBand
from aip.domain.analytics.scoring.score_component import ScoreComponent
from aip.domain.analytics.scoring.weighted_score import WeightedScore
from aip.domain.analytics.statistics.descriptive_statistics import DescriptiveStatistics
from aip.domain.analytics.statistics.outlier_detection import OutlierDetection
from aip.domain.analytics.statistics.weighted_statistics import WeightedStatistics

__all__ = [
    "AnalyticsContext",
    "AnalyticsError",
    "CompositeScore",
    "DescriptiveStatistics",
    "DuplicateRankItemError",
    "ExplainabilityError",
    "Explanation",
    "ExplanationBuilder",
    "ExplanationFactor",
    "InvalidScoreBandError",
    "InvalidWeightError",
    "MetricObservation",
    "MinMaxNormalizer",
    "NormalizationError",
    "NormalizationMethod",
    "OutlierDetection",
    "OutlierMethod",
    "PercentileRank",
    "RankItem",
    "RankingEngine",
    "RankingError",
    "RankingOrder",
    "RankingResult",
    "RobustScaler",
    "ScoreBand",
    "ScoreComponent",
    "ScoreDirection",
    "ScoringError",
    "StatisticsError",
    "TieBreaker",
    "WeightedScore",
    "WeightedStatistics",
    "ZScoreNormalizer",
]
