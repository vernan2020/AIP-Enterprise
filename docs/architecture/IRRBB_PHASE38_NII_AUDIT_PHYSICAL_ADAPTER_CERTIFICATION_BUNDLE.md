# IRRBB Phase 38 — NII Audit Physical Adapter Certification Bundle

## Objective

Phase 38 adds a source-neutral, positive-only certification bundle for one already activated physical NII audit persistence adapter.

The bundle consolidates, without duplicating state, the exact chain already established by prior phases:

- persistence readiness assessment;
- serialization compatibility certificate;
- persistence activation authorization;
- physical adapter descriptor;
- activated repository binding;
- traceable certification evidence references.

No physical persistence technology is selected or implemented by this phase.

## Composition

`NIIRunAuditPhysicalAdapterCertificationBundle` contains:

- `certification_reference` — identity of this certification event;
- `activated_persistence` — the exact Phase 37 activated binding;
- `evidence_references` — canonical, unique trace references used to support certification.

Readiness, compatibility, authorization, descriptor and repository are exposed as derived properties from the activated binding. They are deliberately not copied into parallel fields.

This prevents drift between duplicated certification state.

## Certification service

`NIIRunAuditPhysicalAdapterCertificationService.certify(...)` is fail-closed.

Certification requires:

1. nonblank certification identity;
2. nonempty, unique evidence references;
3. READY persistence assessment;
4. exact readiness adapter identity = activated descriptor identity;
5. exact authorization configuration adapter identity = activated descriptor identity;
6. exact serialization schema contract = descriptor schema contract;
7. exact codec identity = descriptor codec identity;
8. exact integrity identity = descriptor integrity identity;
9. explicit readiness evidence for every required persistence capability;
10. exactly one readiness evidence item per required capability;
11. evidence coverage of the activation configuration `source_reference`;
12. evidence coverage of the schema contract `source_reference`;
13. evidence coverage of every source reference used by the readiness assessment;
14. evidence coverage of every transformer reference required by historical schema compatibility.

The required persistence capability perimeter is the complete `REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS` set from Phase 30. A manually constructed `READY` assessment that does not carry explicit evidence for all required capabilities cannot cross Phase 38.

Evidence references are canonicalized lexicographically in the resulting immutable bundle.

## Positive-only semantics

There is no `CERTIFIED=False` object.

A certification bundle exists only when every prerequisite succeeds. Missing prerequisite evidence, incomplete readiness evidence or an identity mismatch raises `NIIRunAuditPhysicalAdapterCertificationError` and produces no bundle.

This makes possession of a valid bundle an explicit capability indicating that one exact activated adapter has passed this certification boundary.

## Important distinction

Phase 38 certifies the internal consistency and traceability of an already activated physical adapter candidate. It does **not** prove that a production database, infrastructure environment or operational deployment has been approved.

External infrastructure evidence remains necessary before a concrete implementation may be promoted to production.

## Explicit non-goals

Phase 38 does not implement or select:

- PostgreSQL or another database;
- SQLAlchemy or another ORM;
- Alembic or physical migrations;
- DSNs or credentials;
- connection pools;
- network endpoints;
- runtime dependency injection;
- application startup activation;
- backup/restore implementation;
- REST/API/UI integration;
- serialization format;
- production integrity algorithm;
- external data integrations blocked by Issue #66.

## Resulting chain

The controlled path is now:

`readiness + serialization compatibility`

→ `Phase 36 persistence activation authorization`

→ `Phase 37 exact physical adapter activation`

→ `Phase 38 immutable physical adapter certification bundle`

A future physical implementation must still provide its own concrete infrastructure evidence and pass all existing gates before production use.
