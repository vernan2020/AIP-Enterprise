# IRRBB Phase 35 — NII Audit Serialization Compatibility Certification

## Objective

Phase 35 introduces a source-neutral static certification boundary for NII audit serialization configurations before any physical persistence adapter is considered eligible for use.

The certification proves that one declared configuration can consume the complete readable schema perimeter defined by the Phase 32 schema-evolution contract and the Phase 34 migration boundary.

## Certified perimeter

A certificate binds:

- the exact `NIIAuditSchemaEvolutionContract`;
- the codec reference;
- the integrity-boundary reference;
- every declared readable schema version;
- the unique migration path from each historical version to the current schema;
- the exact transformer reference assigned to every migration step used by those paths.

The certificate is produced only after all validations succeed. There is no optimistic or partially certified state.

## Codec semantics

The codec is required to support the **current schema version**.

It is intentionally **not** required to decode every historical schema version directly. Phase 34 migrates historical payload bytes through the unique approved migration path and only then decodes the current-schema envelope through the Phase 33 codec boundary.

Requiring historical codec support would duplicate the migration responsibility and would incorrectly couple the codec to legacy physical representations.

## Migration coverage

Phase 35 reuses `NIIAuditSchemaEvolutionService.validate_contract()` and `migration_path()`.

Therefore:

- every declared readable version must reach the current schema;
- each readable version must have exactly one migration path;
- ambiguous paths fail closed;
- the current schema requires no migration;
- every migration step actually required by the readable perimeter must resolve to a transformer bound to that exact step;
- every transformer must expose a nonblank audit reference.

Each required migration step is resolved exactly once during certification. If the same step participates in several historical paths, the same certified transformer identity is reused in every path entry.

## Static-only behavior

Compatibility certification does not:

- encode an audit record;
- decode an audit record;
- execute a payload migration;
- calculate or verify a payload digest;
- access persisted rows;
- connect to a database;
- choose a serialization format;
- choose a cryptographic or integrity algorithm;
- create runtime dependency-injection wiring.

It validates declared capabilities and identities only.

## Fail-closed rules

Certification fails if:

- the schema-evolution graph is incomplete or ambiguous;
- the codec reference is blank;
- the codec declares no supported schemas;
- the codec does not support the current schema;
- the integrity reference is blank;
- a required transformer cannot be resolved;
- the resolver returns a transformer for another migration step;
- a transformer reference is blank.

A failure does not produce a compatibility certificate.

## Relationship to previous phases

```text
Phase 32 schema evolution contract
            |
            v
Phase 35 static compatibility certification
            |
            +-- current schema -> codec support
            |
            +-- historical schema -> unique migration path
                                      -> exact transformer identities
            |
            v
Phase 34 historical migration + decode orchestration
            |
            v
Phase 33 serialization envelope boundary
```

## Non-goals

Phase 35 does not add:

- PostgreSQL or another database adapter;
- SQLAlchemy/ORM models;
- Alembic or another migration engine;
- JSON, MessagePack, protobuf or another mandated serialization format;
- a mandated production integrity algorithm;
- encryption or key management;
- physical migration of persisted data;
- REST/API/UI integration;
- runtime activation;
- any external source adapter blocked by Issue #66.

## Production implication

A future physical persistence adapter may use this certificate as one prerequisite for activation, but the certificate alone is not production approval. Physical storage behavior, transactionality, retention, access control, operational recovery, source certification and reconciliation remain separate gates.
