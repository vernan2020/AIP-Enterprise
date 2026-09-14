from __future__ import annotations

from dataclasses import dataclass

import pytest

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationAuthorization,
    NIIRunAuditPersistenceActivationConfiguration,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceReadinessAssessment,
    NIIAuditPersistenceReadinessStatus,
)
from aip.domain.irrbb.nii_audit_physical_persistence import (
    NIIRunAuditPhysicalPersistenceActivationError,
    NIIRunAuditPhysicalPersistenceDescriptor,
)
from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIAuditReadableSchemaCompatibility,
    NIIRunAuditSerializationCompatibilityCertificate,
)
from aip.domain.irrbb.nii_run_audit import NIIRunAuditRepositoryPutResult
from aip.domain.irrbb.services.nii_audit_physical_persistence_activation_service import (
    NIIRunAuditPhysicalPersistenceActivationService,
)


class _Repository:
    def get_by_run_reference(self, *, run_reference: str):
        return None

    def put_if_absent(self, *, record):
        return NIIRunAuditRepositoryPutResult(created=True, record=record)


@dataclass
class _Adapter:
    descriptor: NIIRunAuditPhysicalPersistenceDescriptor
    repository: _Repository
    activation_calls: int = 0
    received_authorization: NIIRunAuditPersistenceActivationAuthorization | None = None

    def activate(self, *, authorization: NIIRunAuditPersistenceActivationAuthorization):
        self.activation_calls += 1
        self.received_authorization = authorization
        return self.repository


def _schema_contract(reference: str = "nii-audit") -> NIIAuditSchemaEvolutionContract:
    version = NIIAuditSchemaVersion(schema_reference=reference, version=1)
    return NIIAuditSchemaEvolutionContract(
        current_version=version,
        readable_versions=frozenset({version}),
        migration_steps=(),
        source_reference="schema-policy",
    )


def _authorization() -> NIIRunAuditPersistenceActivationAuthorization:
    schema_contract = _schema_contract()
    configuration = NIIRunAuditPersistenceActivationConfiguration(
        adapter_reference="adapter-v1",
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        source_reference="activation-policy",
    )
    readiness = NIIAuditPersistenceReadinessAssessment(
        adapter_reference="adapter-v1",
        status=NIIAuditPersistenceReadinessStatus.READY,
        certified_requirements=REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
        missing_requirements=frozenset(),
        evidence=(),
    )
    compatibility = NIIRunAuditSerializationCompatibilityCertificate(
        schema_contract=schema_contract,
        codec_reference="codec-v1",
        integrity_reference="integrity-v1",
        readable_schema_compatibility=(
            NIIAuditReadableSchemaCompatibility(
                source_version=schema_contract.current_version,
                migration_steps=(),
                transformer_references=(),
            ),
        ),
    )
    return NIIRunAuditPersistenceActivationAuthorization(
        configuration=configuration,
        readiness=readiness,
        compatibility=compatibility,
    )


def _descriptor(
    *,
    adapter_reference: str = "adapter-v1",
    schema_contract: NIIAuditSchemaEvolutionContract | None = None,
    codec_reference: str = "codec-v1",
    integrity_reference: str = "integrity-v1",
) -> NIIRunAuditPhysicalPersistenceDescriptor:
    return NIIRunAuditPhysicalPersistenceDescriptor(
        adapter_reference=adapter_reference,
        schema_contract=schema_contract or _schema_contract(),
        codec_reference=codec_reference,
        integrity_reference=integrity_reference,
    )


def test_exact_authorized_adapter_is_activated_once() -> None:
    authorization = _authorization()
    repository = _Repository()
    adapter = _Adapter(
        descriptor=_descriptor(schema_contract=authorization.configuration.schema_contract),
        repository=repository,
    )

    activated = NIIRunAuditPhysicalPersistenceActivationService.activate(
        authorization=authorization,
        adapter=adapter,
    )

    assert adapter.activation_calls == 1
    assert adapter.received_authorization is authorization
    assert activated.authorization is authorization
    assert activated.descriptor is adapter.descriptor
    assert activated.repository is repository


@pytest.mark.parametrize(
    ("descriptor", "message"),
    [
        (_descriptor(adapter_reference="adapter-v2"), "adapter identity mismatch"),
        (_descriptor(schema_contract=_schema_contract("other-schema")), "schema contract mismatch"),
        (_descriptor(codec_reference="codec-v2"), "codec identity mismatch"),
        (_descriptor(integrity_reference="integrity-v2"), "integrity identity mismatch"),
    ],
)
def test_identity_mismatch_blocks_before_adapter_activation(
    descriptor: NIIRunAuditPhysicalPersistenceDescriptor,
    message: str,
) -> None:
    authorization = _authorization()
    adapter = _Adapter(descriptor=descriptor, repository=_Repository())

    with pytest.raises(NIIRunAuditPhysicalPersistenceActivationError, match=message):
        NIIRunAuditPhysicalPersistenceActivationService.activate(
            authorization=authorization,
            adapter=adapter,
        )

    assert adapter.activation_calls == 0
    assert adapter.received_authorization is None


def test_descriptor_requires_nonblank_physical_identities() -> None:
    schema_contract = _schema_contract()

    with pytest.raises(ValueError, match="adapter_reference"):
        NIIRunAuditPhysicalPersistenceDescriptor(
            adapter_reference=" ",
            schema_contract=schema_contract,
            codec_reference="codec-v1",
            integrity_reference="integrity-v1",
        )
    with pytest.raises(ValueError, match="codec_reference"):
        NIIRunAuditPhysicalPersistenceDescriptor(
            adapter_reference="adapter-v1",
            schema_contract=schema_contract,
            codec_reference=" ",
            integrity_reference="integrity-v1",
        )
    with pytest.raises(ValueError, match="integrity_reference"):
        NIIRunAuditPhysicalPersistenceDescriptor(
            adapter_reference="adapter-v1",
            schema_contract=schema_contract,
            codec_reference="codec-v1",
            integrity_reference=" ",
        )
