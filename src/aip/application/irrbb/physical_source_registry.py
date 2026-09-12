from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aip.application.irrbb.source_certification import IRRBBSourcePerimeter


class IRRBBPhysicalSourceKind(str, Enum):
    """Supported physical source technologies without adapter-specific behavior."""

    POWER_BI_SEMANTIC_MODEL = "POWER_BI_SEMANTIC_MODEL"
    EXCEL_WORKBOOK = "EXCEL_WORKBOOK"
    PORTFOLIO_MASTER = "PORTFOLIO_MASTER"


class IRRBBPhysicalSourceSegment(str, Enum):
    """Institutional RTILB position segments requiring independent physical sources."""

    CREDIT = "CREDIT"
    TERM_DEPOSIT = "TERM_DEPOSIT"
    BORROWING = "BORROWING"
    INVESTMENT = "INVESTMENT"

    @property
    def certification_perimeter(self) -> IRRBBSourcePerimeter:
        """Map the physical segment to the existing canonical certification perimeter."""

        if self is IRRBBPhysicalSourceSegment.CREDIT:
            return IRRBBSourcePerimeter.CREDIT
        if self in {
            IRRBBPhysicalSourceSegment.TERM_DEPOSIT,
            IRRBBPhysicalSourceSegment.BORROWING,
        }:
            return IRRBBSourcePerimeter.LIABILITY
        return IRRBBSourcePerimeter.INVESTMENT


@dataclass(frozen=True, slots=True)
class IRRBBPhysicalSourceDescriptor:
    """Governed identity of one candidate physical source.

    ``configuration_key`` is an opaque deployment key. It is deliberately not a
    workstation path, URL, credential, workspace identifier or connector secret.
    Runtime composition must resolve it outside the application layer.
    """

    source_id: str
    segment: IRRBBPhysicalSourceSegment
    kind: IRRBBPhysicalSourceKind
    logical_name: str
    configuration_key: str
    owner: str | None = None
    location: str | None = None

    def __post_init__(self) -> None:
        self._require_text("source_id", self.source_id)
        self._require_text("logical_name", self.logical_name)
        self._require_text("configuration_key", self.configuration_key)
        self._validate_optional_text("owner", self.owner)
        self._validate_optional_text("location", self.location)

    @property
    def certification_perimeter(self) -> IRRBBSourcePerimeter:
        return self.segment.certification_perimeter

    @staticmethod
    def _require_text(field_name: str, value: str) -> None:
        if not value.strip():
            raise ValueError(f"physical source {field_name} is required")

    @staticmethod
    def _validate_optional_text(field_name: str, value: str | None) -> None:
        if value is not None and not value.strip():
            raise ValueError(f"physical source {field_name} cannot be blank")


class IRRBBPhysicalSourceRegistry:
    """Fail-closed registry of physical source identities by RTILB segment."""

    def __init__(self, sources: tuple[IRRBBPhysicalSourceDescriptor, ...]) -> None:
        if not sources:
            raise ValueError("physical source registry requires at least one source")

        source_ids = tuple(item.source_id for item in sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("physical source registry source_id values must be unique")

        segments = tuple(item.segment for item in sources)
        if len(set(segments)) != len(segments):
            raise ValueError("physical source registry segments must be unique")

        configuration_keys = tuple(item.configuration_key for item in sources)
        if len(set(configuration_keys)) != len(configuration_keys):
            raise ValueError("physical source registry configuration_key values must be unique")

        self._sources = sources
        self._sources_by_segment = {item.segment: item for item in sources}

    @property
    def sources(self) -> tuple[IRRBBPhysicalSourceDescriptor, ...]:
        return self._sources

    def require(self, segment: IRRBBPhysicalSourceSegment) -> IRRBBPhysicalSourceDescriptor:
        """Return the configured source for a segment or fail instead of falling back."""

        try:
            return self._sources_by_segment[segment]
        except KeyError as exc:
            raise KeyError(
                f"no physical IRRBB source registered for segment {segment.value}"
            ) from exc
