# IRRBB Phase 37 — NII Audit Physical Persistence Boundary

## Objective

Define the source-neutral boundary through which an already authorized NII audit persistence configuration may be bound to one physical adapter.

Phase 37 consumes the positive authorization created by Phase 36. It does not select, instantiate, configure or certify PostgreSQL, SQLAlchemy or any other concrete storage technology.

## Capability-gated activation

A physical adapter must expose an immutable technical descriptor with:

- `adapter_reference`
- `schema_contract`
- `codec_reference`
- `integrity_reference`

The adapter protocol does not expose a repository directly. Instead it exposes:

```python
activate(*, authorization: NIIRunAuditPersistenceActivationAuthorization) -> NIIRunAuditRepository
```

The Phase 37 activation service first reconciles the physical adapter descriptor against the exact Phase 36 authorization configuration. Only after every identity matches does the service invoke `adapter.activate(...)`.

This makes the Phase 36 authorization object a capability token at the domain boundary.

## Fail-closed identity reconciliation

Activation is rejected before the physical adapter is called when any of the following differ:

- adapter identity;
- schema evolution contract;
- serialization codec identity;
- integrity mechanism identity.

There is no fallback, substitution, default adapter, default schema, default codec or default integrity mechanism.

## Result

Successful activation returns `NIIRunAuditActivatedPhysicalPersistence`, which binds:

- the exact Phase 36 authorization;
- the physical adapter descriptor;
- the resulting source-neutral `NIIRunAuditRepository`.

The activated binding revalidates the direct structural identity invariants.

## Relationship to existing phases

- Phase 28 defines the immutable audit repository boundary.
- Persistence readiness certifies required physical capabilities.
- Repository conformance provides executable behavioral verification.
- Schema evolution and serialization phases define versioning, migration and codec/integrity contracts.
- Phase 35 certifies serialization compatibility.
- Phase 36 authorizes one exact persistence configuration.
- Phase 37 defines how one exact physical adapter may consume that authorization.

Phase 37 does not weaken or duplicate any prior certification.

## Explicit non-goals

Phase 37 does **not**:

- implement PostgreSQL;
- implement SQLAlchemy;
- create tables or migrations;
- define DSNs, credentials, pools or transactions;
- open database connections in domain code;
- mandate JSON, MessagePack, database-native JSON or another physical encoding;
- mandate SHA-256, HMAC, signatures or another production integrity mechanism;
- implement runtime dependency injection;
- add API, REST or UI integration;
- automatically activate persistence during application startup;
- modify NII financial methodology or calculations;
- resolve external-source blockers tracked by Issue #66.

## Future physical adapter requirement

A future concrete adapter must independently provide the evidence required by persistence readiness and pass the repository conformance suite. Its declared descriptor must then match an explicit Phase 36 authorization before the Phase 37 boundary permits activation.

This sequence prevents infrastructure choice from bypassing the domain certification chain.
