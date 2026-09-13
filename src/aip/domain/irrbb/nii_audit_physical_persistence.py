from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
)
from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaEvolutionContract
from aip.domain.irrbb.nii_run_audit_ports import NIIRunAuditRepository


class NIIRunAuditPhysicalPersistenceActivationError(ValueError):
    """Raised when an authorized physical persistence adapter cannot be activated."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditPhysicalPersistenceDescriptor:
    """Declared technical identity of one physical NII audit persistence adapter."""

    adapter_reference: str
    schema_contract: NIIAuditSchemaEvolutionContract
    codec_reference: str
    integrity_reference: str

    def __post_init__(self) -> None:
        if not self.adapter_reference.strip():
            raise ValueError("NII audit physical adapter_reference is required")
        if not self.codec_reference.strip():
            raise ValueError("NII audit physical codec_reference is required")
        if not self.integrity_reference.strip():
            raise ValueError("NII audit physical integrity_reference is required")


class NIIRunAuditPhysicalPersistenceAdapter(Protocol):
    """Capability-gated boundary implemented by a physical persistence adapter.

    A concrete adapter must expose the exact technical identities it implements and
    must require the Phase 36 authorization object before returning its repository.
    The protocol deliberately does not prescribe a database, ORM, connection model,
    serialization format, or integrity algorithm.
    """

    @property
    def descriptor(self) -> NIIRunAuditPhysicalPersistenceDescriptor: ...

    def activate(
        self,
        *,
        authorization: NIIRunAuditPersistenceActivationAuthorization,
    ) -> NIIRunAuditRepository: ...


@dataclass(frozen=True, slots=True)
class NIIRunAuditActivatedPhysicalPersistence:
    """Bound repository produced only after exact authorization/adapter reconciliation."""

    authorization: NIIRunAuditPersistenceActivationAuthorization
    descriptor: NIIRunAuditPhysicalPersistenceDescriptor
    repository: NIIRunAuditRepository

    def __post_init__(self) -> None:
        configuration = self.authorization.configuration
        if self.descriptor.adapter_reference != configuration.adapter_reference:
            raise ValueError("Activated NII audit persistence adapter identity mismatch")
        if self.descriptor.schema_contract != configuration.schema_contract:
            raise ValueError("Activated NII audit persistence schema contract mismatch")
        if self.descriptor.codec_reference != configuration.codec_reference:
            raise ValueError("Activated NII audit persistence codec identity mismatch")
        if self.descriptor.integrity_reference != configuration.integrity_reference:
            raise ValueError("Activated NII audit persistence integrity identity mismatch")
