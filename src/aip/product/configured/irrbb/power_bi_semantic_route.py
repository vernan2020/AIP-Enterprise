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
CAPTACIONES_INSPECTION_SOURCE_ID = "coopealianza.liability.powerbi.captaciones"
CAPTACIONES_INSPECTION_CONFIGURATION_KEY = "irrbb.sources.captaciones.power_bi"


class PowerBISemanticQueryTransport(str, Enum):
    """Approved transport contract for governed Power BI semantic-model access."""

    EXECUTE_DAX_QUERIES_ARROW = "EXECUTE_DAX_QUERIES_ARROW"


@dataclass(frozen=True, slots=True)
class PowerBISemanticModelRoute:
    """Deployment-resolved route to one Power BI semantic model.

    The route contains non-secret identifiers plus an opaque authentication-profile
    reference. ``workspace_id`` is optional so models in My workspace can use the
    Microsoft dataset-only Execute DAX Queries endpoint. Models in another workspace
    continue to use the explicit group/workspace route.

    Credentials, bearer tokens, client secrets and tenant secrets are intentionally
    outside this contract.
    """

    configuration_key: str
    workspace_id: UUID | None
    dataset_id: UUID
    authentication_profile_key: str
    transport: PowerBISemanticQueryTransport = (
        PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW
    )

    def __post_init__(self) -> None:
        self._require_reference_key("configuration_key", self.configuration_key)
        self._require_reference_key("authentication_profile_key", self.authentication_profile_key)
        if self.workspace_id is not None:
            self._require_non_nil_uuid("workspace_id", self.workspace_id)
        self._require_non_nil_uuid("dataset_id", self.dataset_id)
        if self.transport is not PowerBISemanticQueryTransport.EXECUTE_DAX_QUERIES_ARROW:
            raise ValueError("unsupported Power BI semantic query transport")

    @classmethod
    def from_strings(
        cls,
        *,
        configuration_key: str,
        workspace_id: str | None,
        dataset_id: str,
        authentication_profile_key: str,
    ) -> PowerBISemanticModelRoute:
        """Build a validated route from deployment configuration strings."""

        return cls(
            configuration_key=configuration_key,
            workspace_id=(
                None if workspace_id is None else cls._parse_uuid("workspace_id", workspace_id)
            ),
            dataset_id=cls._parse_uuid("dataset_id", dataset_id),
            authentication_profile_key=authentication_profile_key,
        )

    @property
    def execute_dax_queries_url(self) -> str:
        """Return the pinned Microsoft Arrow endpoint for this semantic model."""

        if self.workspace_id is None:
            return (
                f"{_POWER_BI_API_ORIGIN}/v1.0/myorg/datasets/{self.dataset_id}" "/executeDaxQueries"
            )
        return (
            f"{_POWER_BI_API_ORIGIN}/v1.0/myorg/groups/{self.workspace_id}"
            f"/datasets/{self.dataset_id}/executeDaxQueries"
        )

    @property
    def safe_reference(self) -> str:
        """Return a diagnostic route reference containing no authentication material."""

        if self.workspace_id is None:
            return f"powerbi://dataset/{self.dataset_id}"
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
class PowerBISemanticModelInspectionTarget:
    """Provider model identity that may exist before canonical IRRBB classification.

    Inspection targets deliberately separate provider discovery from production
    financial mapping. ``canonical_descriptor`` is present only when the provider
    model is already governed as one exact IRRBB physical source. A model such as
    Captaciones can therefore be inspected without pretending that every product in
    the model is a term deposit or any other canonical segment.
    """

    inspection_source_id: str
    logical_name: str
    route: PowerBISemanticModelRoute
    canonical_descriptor: IRRBBPhysicalSourceDescriptor | None = None

    def __post_init__(self) -> None:
        self._require_identity("inspection_source_id", self.inspection_source_id)
        if not isinstance(self.logical_name, str) or not self.logical_name.strip():
            raise ValueError("Power BI inspection target logical_name is required")
        if self.logical_name != self.logical_name.strip():
            raise ValueError("Power BI inspection target logical_name cannot have outer whitespace")

        descriptor = self.canonical_descriptor
        if descriptor is None:
            return
        if descriptor.kind is not IRRBBPhysicalSourceKind.POWER_BI_SEMANTIC_MODEL:
            raise ValueError("canonical Power BI inspection target must be a semantic-model source")
        expected_descriptor = _CANONICAL_SEMANTIC_SOURCES.get(descriptor.segment)
        if expected_descriptor is None or descriptor != expected_descriptor:
            raise ValueError("canonical Power BI inspection target is not an exact governed source")
        if descriptor.source_id != self.inspection_source_id:
            raise ValueError("inspection_source_id does not match canonical descriptor")
        if descriptor.logical_name != self.logical_name:
            raise ValueError("logical_name does not match canonical descriptor")
        if descriptor.configuration_key != self.route.configuration_key:
            raise ValueError("route configuration_key does not match canonical descriptor")

    @property
    def canonical_mapping_authorized(self) -> bool:
        """Whether this target already has an exact governed canonical source."""

        return self.canonical_descriptor is not None

    @property
    def safe_reference(self) -> str:
        """Return non-secret provider lineage without authentication material."""

        return f"{self.inspection_source_id}@{self.route.safe_reference}"

    @staticmethod
    def _require_identity(field_name: str, value: str) -> None:
        if not isinstance(value, str) or _REFERENCE_KEY_PATTERN.fullmatch(value) is None:
            raise ValueError(f"Power BI inspection target {field_name} must be an opaque identity")


def institutional_power_bi_inspection_targets(
    *,
    credit_dataset_id: str,
    captaciones_dataset_id: str,
    authentication_profile_key: str,
    credit_workspace_id: str | None = None,
    captaciones_workspace_id: str | None = None,
) -> tuple[PowerBISemanticModelInspectionTarget, PowerBISemanticModelInspectionTarget]:
    """Build deployment-resolved Crédito and Captaciones inspection targets.

    Crédito retains its existing canonical CREDIT binding. Captaciones is intentionally
    inspection-only until governed metadata proves which canonical liability segments
    and product mappings are present. Dataset identifiers are supplied by deployment
    configuration and are never embedded as institutional constants in source code.
    """

    credit_route = PowerBISemanticModelRoute.from_strings(
        configuration_key=CREDIT_SEMANTIC_MODEL_SOURCE.configuration_key,
        workspace_id=credit_workspace_id,
        dataset_id=credit_dataset_id,
        authentication_profile_key=authentication_profile_key,
    )
    captaciones_route = PowerBISemanticModelRoute.from_strings(
        configuration_key=CAPTACIONES_INSPECTION_CONFIGURATION_KEY,
        workspace_id=captaciones_workspace_id,
        dataset_id=captaciones_dataset_id,
        authentication_profile_key=authentication_profile_key,
    )
    return (
        PowerBISemanticModelInspectionTarget(
            inspection_source_id=CREDIT_SEMANTIC_MODEL_SOURCE.source_id,
            logical_name=CREDIT_SEMANTIC_MODEL_SOURCE.logical_name,
            route=credit_route,
            canonical_descriptor=CREDIT_SEMANTIC_MODEL_SOURCE,
        ),
        PowerBISemanticModelInspectionTarget(
            inspection_source_id=CAPTACIONES_INSPECTION_SOURCE_ID,
            logical_name="Captaciones",
            route=captaciones_route,
            canonical_descriptor=None,
        ),
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
