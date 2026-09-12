from __future__ import annotations

from aip.domain.irrbb.nii_audit_schema_evolution import (
    NIIAuditSchemaEvolutionContract,
    NIIAuditSchemaMigrationStep,
    NIIAuditSchemaVersion,
)


class NIIAuditSchemaEvolutionService:
    """Resolve deterministic declared upgrade paths without performing migrations."""

    @classmethod
    def migration_path(
        cls,
        *,
        contract: NIIAuditSchemaEvolutionContract,
        source_version: NIIAuditSchemaVersion,
    ) -> tuple[NIIAuditSchemaMigrationStep, ...]:
        if source_version not in contract.readable_versions:
            raise ValueError("NII audit source schema version is not declared readable")
        if source_version == contract.current_version:
            return ()

        paths = cls._paths_to_current(
            contract=contract,
            current=source_version,
            visited=frozenset(),
        )
        if not paths:
            raise ValueError("No declared NII audit migration path reaches current schema")
        if len(paths) != 1:
            raise ValueError("NII audit migration path is ambiguous")
        return paths[0]

    @classmethod
    def validate_contract(cls, *, contract: NIIAuditSchemaEvolutionContract) -> None:
        for version in contract.readable_versions:
            cls.migration_path(contract=contract, source_version=version)

    @classmethod
    def _paths_to_current(
        cls,
        *,
        contract: NIIAuditSchemaEvolutionContract,
        current: NIIAuditSchemaVersion,
        visited: frozenset[NIIAuditSchemaVersion],
    ) -> tuple[tuple[NIIAuditSchemaMigrationStep, ...], ...]:
        if current == contract.current_version:
            return ((),)
        if current in visited:
            return ()

        next_visited = visited | {current}
        paths: list[tuple[NIIAuditSchemaMigrationStep, ...]] = []
        for step in contract.migration_steps:
            if step.source != current:
                continue
            for suffix in cls._paths_to_current(
                contract=contract,
                current=step.target,
                visited=next_visited,
            ):
                paths.append((step, *suffix))
        return tuple(paths)
