from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class NIIAuditSchemaVersion:
    """Ordered version identifier for one logical NII audit persistence schema."""

    schema_reference: str
    version: int

    def __post_init__(self) -> None:
        if not self.schema_reference.strip():
            raise ValueError("NII audit schema_reference is required")
        if self.version < 1:
            raise ValueError("NII audit schema version must be positive")


@dataclass(frozen=True, slots=True)
class NIIAuditSchemaMigrationStep:
    """Explicit approved upgrade step between two versions of one schema."""

    source: NIIAuditSchemaVersion
    target: NIIAuditSchemaVersion
    source_reference: str

    def __post_init__(self) -> None:
        if self.source.schema_reference != self.target.schema_reference:
            raise ValueError("NII audit migration cannot cross schema references")
        if self.target.version <= self.source.version:
            raise ValueError("NII audit migration must advance schema version")
        if not self.source_reference.strip():
            raise ValueError("NII audit migration source_reference is required")


@dataclass(frozen=True, slots=True)
class NIIAuditSchemaEvolutionContract:
    """Declared readable schema versions and explicit upgrade graph for one adapter."""

    current_version: NIIAuditSchemaVersion
    readable_versions: frozenset[NIIAuditSchemaVersion]
    migration_steps: tuple[NIIAuditSchemaMigrationStep, ...]
    source_reference: str

    def __post_init__(self) -> None:
        if not self.source_reference.strip():
            raise ValueError("NII audit schema contract source_reference is required")
        if not self.readable_versions:
            raise ValueError("NII audit schema contract requires readable versions")
        if self.current_version not in self.readable_versions:
            raise ValueError("Current NII audit schema version must be readable")
        schema_reference = self.current_version.schema_reference
        if any(version.schema_reference != schema_reference for version in self.readable_versions):
            raise ValueError("Readable NII audit versions must belong to one schema")

        seen_edges: set[tuple[NIIAuditSchemaVersion, NIIAuditSchemaVersion]] = set()
        for step in self.migration_steps:
            edge = (step.source, step.target)
            if edge in seen_edges:
                raise ValueError("Duplicate NII audit schema migration step")
            seen_edges.add(edge)
            if step.source not in self.readable_versions:
                raise ValueError("Migration source must be a declared readable version")
            if step.target not in self.readable_versions:
                raise ValueError("Migration target must be a declared readable version")
