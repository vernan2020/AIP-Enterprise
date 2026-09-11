from __future__ import annotations

import pytest

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
    NIIAuditSchemaVersion,
)
from aip.domain.irrbb.services.nii_audit_schema_evolution_service import (
    NIIAuditSchemaEvolutionService,
)


def _version(number: int) -> NIIAuditSchemaVersion:
    return NIIAuditSchemaVersion(schema_reference="nii-audit-record", version=number)


def _step(source: int, target: int) -> NIIAuditSchemaMigrationStep:
    return NIIAuditSchemaMigrationStep(
        source=_version(source),
        target=_version(target),
        source_reference=f"migration:{source}-to-{target}",
    )


def _contract(
    *,
    readable: frozenset[NIIAuditSchemaVersion],
    steps: tuple[NIIAuditSchemaMigrationStep, ...],
    current: int = 3,
) -> NIIAuditSchemaEvolutionContract:
    return NIIAuditSchemaEvolutionContract(
        current_version=_version(current),
        readable_versions=readable,
        migration_steps=steps,
        source_reference="policy:nii-audit-schema:v1",
    )


def test_current_version_requires_no_migration() -> None:
    contract = _contract(readable=frozenset({_version(3)}), steps=())

    path = NIIAuditSchemaEvolutionService.migration_path(
        contract=contract,
        source_version=_version(3),
    )

    assert path == ()


def test_resolves_exact_declared_upgrade_path() -> None:
    contract = _contract(
        readable=frozenset({_version(1), _version(2), _version(3)}),
        steps=(_step(1, 2), _step(2, 3)),
    )

    path = NIIAuditSchemaEvolutionService.migration_path(
        contract=contract,
        source_version=_version(1),
    )

    assert path == (_step(1, 2), _step(2, 3))


def test_contract_validation_requires_every_readable_version_to_reach_current() -> None:
    contract = _contract(
        readable=frozenset({_version(1), _version(2), _version(3)}),
        steps=(_step(2, 3),),
    )

    with pytest.raises(ValueError, match="No declared NII audit migration path"):
        NIIAuditSchemaEvolutionService.validate_contract(contract=contract)


def test_ambiguous_migration_path_is_rejected() -> None:
    contract = _contract(
        readable=frozenset({_version(1), _version(2), _version(3)}),
        steps=(_step(1, 3), _step(1, 2), _step(2, 3)),
    )

    with pytest.raises(ValueError, match="migration path is ambiguous"):
        NIIAuditSchemaEvolutionService.migration_path(
            contract=contract,
            source_version=_version(1),
        )


def test_undeclared_source_version_is_rejected() -> None:
    contract = _contract(readable=frozenset({_version(3)}), steps=())

    with pytest.raises(ValueError, match="not declared readable"):
        NIIAuditSchemaEvolutionService.migration_path(
            contract=contract,
            source_version=_version(2),
        )


def test_cross_schema_migration_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot cross schema references"):
        NIIAuditSchemaMigrationStep(
            source=NIIAuditSchemaVersion(schema_reference="schema-a", version=1),
            target=NIIAuditSchemaVersion(schema_reference="schema-b", version=2),
            source_reference="migration:a-to-b",
        )


def test_backward_or_same_version_migration_is_rejected() -> None:
    with pytest.raises(ValueError, match="must advance schema version"):
        _step(2, 2)


def test_migration_endpoints_must_be_declared_readable() -> None:
    with pytest.raises(ValueError, match="Migration source must be a declared readable"):
        _contract(
            readable=frozenset({_version(2), _version(3)}),
            steps=(_step(1, 2), _step(2, 3)),
        )
