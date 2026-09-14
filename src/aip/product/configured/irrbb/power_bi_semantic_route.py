from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from aip.application.irrbb.physical_source_registry import (
    IRRBBPhysicalSourceDescriptor,
    IRRBBPhysicalSourceKind,
    IRRBBPhysicalSourceSegment,
)
from aip.product.configured.irrbb.physical_source_registry import (
    CREDIT_SEMANTIC_MODEL_SOURCE,
    TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
)

_POWER_BI_API_ORIGIN = "https://api.powerbi.com"
_REFERENCE_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_CANONICAL_SEMANTIC_SOURCES = {
    IRRBBPhysicalSourceSegment.CREDIT: CREDIT_SEMANTIC_MODEL_SOURCE,
    IRRBBPhysicalSourceSegment.TERM_DEPOSIT: TERM_DEPOSIT_SEMANTIC_MODEL_SOURCE,
}


class PowerBISemanticQueryTransport(str, Enum):
    """Approved transport contract for governed Power BI semantic-model access."""

    EXECUTE_DAX_QUERIES_ARROW = "EXECUTE_DAX_QUERIES_ARROW"


@dataclass(frozen=True, slots=True)
class PowerBISemanticModelRoute:
    """Deployment-resolved route to one Power BI semantic model.

    The route contains non-secret identifiers plus an opaque authentication-profile
    reference. Credentials, bearer tokens, client secrets and tenant secrets are
    intentionally outside this contract.
    """

    configuration_key: str
    workspace_id: UUID
    dataset_id: UUID
    authentication_profile_key: str
    transport: PowerBISemanticQueryTransport = (
        PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW
    )

    def __post_init__(self) -> None:
        self._require_reference_key("configuration_key", self.configuration_key)
        self._require_reference_key(
            "authentication_profile_key", self.authentication_profile_key
        )
        self._require_non_nil_uuid("workspace_id", self.workspace_id)
        self._require_non_nil_uuid("dataset_id", self.dataset_id)
        if self.transport is not PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW:
            raise ValueError("unsupported Power BI semantic query transport")

    @classmethod
    def from_strings(
        cls,
        *,
        configuration_key: str,
        workspace_id: str,
        dataset_id: str,
        authentication_profile_key: str,
    ) -> PowerBISemanticModelRoute:
        """Build a validated route from deployment configuration strings."""

        return cls(
            configuration_key=configuration_key,
            workspace_id=cls._parse_uuid("workspace_id", workspace_id),
            dataset_id=cls._parse_uuid("dataset_id", dataset_id),
            authentication_profile_key=authentication_profile_key,
        )

    @property
    def execute_dax_queries_url(self) -> str:
        """Return the pinned Microsoft endpoint for this workspace/model pair."""

        return (
            f"{_POWER_BI_API_ORIGIN}/v1.0/myorg/groups/{self.workspace_id}"
            f"/datasets/{self.dataset_id}/executeDaxQueries"
        )

    @property
    def safe_reference(self) -> str:
        """Return a diagnostic route reference containing no authentication material."""

        return f"powerbi://workspace/{self.workspace_id}/dataset/{self.dataset_id}"

    @staticmethod
    def _parse_uuid(field_name: str, value: str) -> UUID:
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"Power BI route {field_name} must be a canonical UUID string")
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Power BI route {field_name} must be a canonical UUID string"
            ) from exc
        if str(parsed) != value.lower():
            raise ValueError(f"Power BI route {field_name} must be a canonical UUID string")
        if parsed.int == 0:
            raise ValueError(f"Power BI route {field_name} cannot be the nil UUID")
        return parsed

    @staticmethod
    def _require_non_nil_uuid(field_name: str, value: UUID) -> None:
        if not isinstance(value, UUID):
            raise ValueError(f"Power BI route {field_name} must be a UUID")
        if value.int == 0:
            raise ValueError(f"Power BI route {field_name} cannot be the nil UUID")

    @staticmethod
    def _require_reference_key(field_name: str, value: str) -> None:
        if not isinstance(value, str) or _REFERENCE_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError(
                f"Power BI route {field_name} must be an opaque configuration reference"
            )


@dataclass(frozen=True, slots=True)
class InstitutionalPowerBISemanticRouteBinding:
    """Bind a route to one exact governed institutional semantic-model descriptor."""

    descriptor: IRRBBPhysicalSourceDescriptor
    route: PowerBISemanticModelRoute

    def __post_init__(self) -> None:
        if self.descriptor.kind is not IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL:
            raise ValueError("Power BI route requires a semantic-model physical source")

        expected_descriptor = _CANONICAL_SEMANTIC_SOURCES.get(self.descriptor.segment)
        if expected_descriptor is None or self.descriptor != expected_descriptor:
            raise ValueError(
                "Power BI route descriptor is not an exact governed institutional source"
            )
        if self.route.configuration_key != self.descriptor.configuration_key:
            raise ValueError(
                "Power BI route configuration_key does not match physical source descriptor"
            )

    @property
    def source_reference(self) -> str:
        """Return a non-secret lineage reference for route-level diagnostics."""

        return f"{self.descriptor.source_id}@{self.route.safe_reference}"
