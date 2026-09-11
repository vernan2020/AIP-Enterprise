from __future__ import annotations

from dataclasses import replace

import pytest

from aip.domain.irrbb.nii_audit_persistence_activation import (
    NIIRunAuditPersistenceActivationConfiguration,
    NIIRunAuditPersistenceActivationError,
)
from aip.domain.irrbb.nii_audit_persistence_readiness import (
    REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS,
    NIIAuditPersistenceEvidence,
    NIIAuditPersistenceReadinessAssessment,
    NIIAuditPersistenceReadinessStatus,
    NIIAuditPersistenceRequirement,
)
from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.nii_audit_serialization_compatibility import (
    NIIAuditReadableSchemaCompatibility,
    NIIRunAuditSerializationCompatibilityCertificate,
)
from aip.domain.irrbb.services.nii_audit_persistence_activation_service import (
    NIIRunAuditPersistenceActivationService,
)

_SCHEMA = NIIAuditSchemaVersion("aip.irrbb.nii-audit", 3)


def _schema_contract(
    *,
    source_reference: str = "architecture:phase36:schema",
) -> NIIAuditSchemaEvolutionContract:
    return NIIAuditSchemaEvolutionContract(
        current_version=_SCHEMA,
        readable_versions=frozenset({_SCHEMA}),
        migration_steps=(),
        source_reference=source_reference,
    )


def _readiness(
    *,
    adapter_reference: str = "repository:test:v1",
    ready: bool = True,
) -> NIIAuditPersistenceReadinessAssessment:
    if ready:
        certified = REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS
        missing = frozenset()
        status = NIIAuditPersistenceReadinessStatus.READY
    else:
        missing = frozenset({NIIAuditPersistenceRequirement.MIGRATION_SAFETY})
        certified = REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS - missing
        status = NIIAuditPersistenceReadinessStatus.BLOCKED
    evidence = tuple(
        NIIAuditPersistenceEvidence(
            requirement=requirement,
            source_reference=f"certification:phase36:{requirement.value.lower()}",
        )
        for requirement in sorted(certified, key=lambda item: item.value)
    )
    return NIIAuditPersistenceReadinessAssessment(
        adapter_reference=adapter_reference,
        status=status,
        certified_requirements=certified,
        missing_requirements=missing,
        evidence=evidence,
    )


def _compatibility(
    *,
    schema_contract: NIIAuditSchemaEvolutionContract,
    codec_reference: str = "codec:test:v3",
    integrity_reference: str = "integrity:test:v1",
) -> NIIRunAuditSerializationCompatibilityCertificate:
    return NIIRunAuditSerializationCompatibilityCertificate(
        schema_contract=schema_contract,
        codec_reference=codec_reference,
        integrity_reference=integrity_reference,
        readable_schema_compatibility=(
            NIIAuditReadableSchemaCompatibility(
                source_version=schema_contract.current_version,
                migration_steps=(),
                transformer_references=(),
            ),
        ),
    )


def _configuration(
    *,
    schema_contract: NIIAuditSchemaEvolutionContract,
) -> NIIRunAuditPersistenceActivationConfiguration:
    return NIIRunAuditPersistenceActivationConfiguration(
        adapter_reference="repository:test:v1",
        schema_contract=schema_contract,
        codec_reference="codec:test:v3",
        integrity_reference="integrity:test:v1",
        source_reference="architecture:phase36:activation",
    )


def test_authorizes_exact_ready_compatible_configuration() -> None:
    schema_contract = _schema_contract()
    configuration = _configuration(schema_contract=schema_contract)
    readiness = _readiness()
    compatibility = _compatibility(schema_contract=schema_contract)

    authorization = NIIRunAuditPersistenceActivationService.authorize(
        configuration=configuration,
        readiness=readiness,
        compatibility=compatibility,
    )

    assert authorization.configuration is configuration
    assert authorization.readiness is readiness
    assert authorization.compatibility is compatibility


def test_rejects_blocked_readiness() -> None:
    schema_contract = _schema_contract()

    with pytest.raises(
        NIIRunAuditPersistenceActivationError,
        match="blocked by readiness",
    ):
        NIIRunAuditPersistenceActivationService.authorize(
            configuration=_configuration(schema_contract=schema_contract),
            readiness=_readiness(ready=False),
            compatibility=_compatibility(schema_contract=schema_contract),
        )


def test_rejects_adapter_identity_mismatch() -> None:
    schema_contract = _schema_contract()

    with pytest.raises(
        NIIRunAuditPersistenceActivationError,
        match="adapter identity mismatch",
    ):
        NIIRunAuditPersistenceActivationService.authorize(
            configuration=_configuration(schema_contract=schema_contract),
            readiness=_readiness(adapter_reference="repository:other:v1"),
            compatibility=_compatibility(schema_contract=schema_contract),
        )


def test_rejects_schema_contract_mismatch() -> None:
    schema_contract = _schema_contract()
    other_contract = _schema_contract(source_reference="architecture:phase36:other-schema")

    with pytest.raises(
        NIIRunAuditPersistenceActivationError,
        match="schema contract mismatch",
    ):
        NIIRunAuditPersistenceActivationService.authorize(
            configuration=_configuration(schema_contract=schema_contract),
            readiness=_readiness(),
            compatibility=_compatibility(schema_contract=other_contract),
        )


def test_rejects_codec_identity_mismatch() -> None:
    schema_contract = _schema_contract()

    with pytest.raises(
        NIIRunAuditPersistenceActivationError,
        match="codec identity mismatch",
    ):
        NIIRunAuditPersistenceActivationService.authorize(
            configuration=_configuration(schema_contract=schema_contract),
            readiness=_readiness(),
            compatibility=_compatibility(
                schema_contract=schema_contract,
                codec_reference="codec:other:v3",
            ),
        )


def test_rejects_integrity_identity_mismatch() -> None:
    schema_contract = _schema_contract()

    with pytest.raises(
        NIIRunAuditPersistenceActivationError,
        match="integrity identity mismatch",
    ):
        NIIRunAuditPersistenceActivationService.authorize(
            configuration=_configuration(schema_contract=schema_contract),
            readiness=_readiness(),
            compatibility=_compatibility(
                schema_contract=schema_contract,
                integrity_reference="integrity:other:v1",
            ),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("adapter_reference", " "),
        ("codec_reference", " "),
        ("integrity_reference", " "),
        ("source_reference", " "),
    ),
)
def test_activation_configuration_requires_traceable_identities(
    field: str,
    value: str,
) -> None:
    schema_contract = _schema_contract()
    configuration = _configuration(schema_contract=schema_contract)

    with pytest.raises(ValueError, match="required"):
        replace(configuration, **{field: value})
