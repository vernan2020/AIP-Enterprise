"""Analytics domain package."""

from .enums.normalization_method import NormalizationMethod
from .enums.outlier_method import OutlierMethod
from .enums.ranking_order import RankingOrder
from .enums.score_direction import ScoreDirection
from .exceptions import (
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
from .explainability.explanation import Explanation
from .explainability.explanation_builder import ExplanationBuilder
from .explainability.explanation_factor import ExplanationFactor
from .models.analytics_context import AnalyticsContext
from .models.metric_observation import MetricObservation
from .normalization.min_max import MinMaxNormalizer
from .normalization.percentile_rank import PercentileRank
from .normalization.robust_scaler import RobustScaler
from .normalization.z_score import ZScoreNormalizer
from .ranking.rank_item import RankItem
from .ranking.ranking_engine import RankingEngine
from .ranking.ranking_result import RankingResult
from .ranking.tie_breaker import TieBreaker
from .scoring.composite_score import CompositeScore
from .scoring.score_band import ScoreBand
from .scoring.score_component import ScoreComponent
from .scoring.weighted_score import WeightedScore
from .statistics.descriptive_statistics import DescriptiveStatistics
from .statistics.outlier_detection import OutlierDetection
from .statistics.weighted_statistics import WeightedStatistics

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
