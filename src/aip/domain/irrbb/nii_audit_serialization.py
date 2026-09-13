from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aip.domain.irrbb.nii_audit_schema_evolution import NIIAuditSchemaVersion
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRecord


class NIIRunAuditSerializationError(ValueError):
    """Base error for NII audit serialization boundary violations."""


class NIIRunAuditUnsupportedSchemaError(NIIRunAuditSerializationError):
    """Raised when an envelope schema version is not explicitly supported."""


class NIIRunAuditPayloadIntegrityError(NIIRunAuditSerializationError):
    """Raised when an encoded NII audit payload fails integrity verification."""


@dataclass(frozen=True, slots=True)
class NIIRunAuditSerializationEnvelope:
    """Storage-neutral envelope for one serialized immutable NII audit record."""

    run_reference: str
    schema_version: NIIAuditSchemaVersion
    codec_reference: str
    integrity_reference: str
    payload: bytes
    payload_digest: str

    def __post_init__(self) -> None:
        if not self.run_reference.strip():
            raise ValueError("NII audit serialization run_reference is required")
        if not self.codec_reference.strip():
            raise ValueError("NII audit serialization codec_reference is required")
        if not self.integrity_reference.strip():
            raise ValueError("NII audit serialization integrity_reference is required")
        if not self.payload:
            raise ValueError("NII audit serialization payload is required")
        if not self.payload_digest.strip():
            raise ValueError("NII audit serialization payload_digest is required")


class NIIRunAuditRecordCodec(Protocol):
    """Codec boundary for physical representations of NIIRunAuditRecord."""

    @property
    def reference(self) -> str: ...

    @property
    def supported_schema_versions(self) -> frozenset[NIIAuditSchemaVersion]: ...

    def encode(
        self,
        *,
        record: NIIRunAuditRecord,
        schema_version: NIIAuditSchemaVersion,
    ) -> bytes: ...

    def decode(
        self,
        *,
        payload: bytes,
        schema_version: NIIAuditSchemaVersion,
    ) -> NIIRunAuditRecord: ...


class NIIRunAuditPayloadIntegrity(Protocol):
    """Integrity boundary for serialized NII audit payload bytes."""

    @property
    def reference(self) -> str: ...

    def digest(self, *, payload: bytes) -> str: ...

    def verify(self, *, payload: bytes, expected_digest: str) -> bool: ...
