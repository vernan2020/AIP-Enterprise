# IRRBB Phase 40 — NII Audit Physical Adapter Production Promotion Authorization

## Objective

Phase 40 introduces a source-neutral, positive-only authorization gate between the
Phase 39 production-readiness assessment and any future production deployment or
runtime activation work.

The gate answers one narrow question:

> Has one exact physical adapter candidate, already assessed as `READY` for one
> target environment, accumulated the complete governance evidence required to be
> authorized for production promotion?

An authorization is a domain proof only. It is not a deployment instruction and
has no infrastructure side effects.

## Inputs

The authorization service consumes:

1. one `NIIRunAuditPhysicalAdapterProductionReadinessAssessment` from Phase 39;
2. one non-blank authorization reference; and
3. evidence covering every mandatory promotion-authorization requirement.

The Phase 39 assessment carries the exact Phase 38 certification bundle, adapter
identity, and target-environment identity forward by composition. Phase 40 does
not duplicate those identities.

## Mandatory authorization evidence

Phase 40 requires traceable source references for all of the following:

- change authorization recorded;
- risk-owner authorization recorded;
- operations-owner authorization recorded;
- deployment window authorized; and
- rollback authority confirmed.

The domain stores only references to evidence. It does not store credentials,
secrets, approval payloads, certificates, tickets, or external-system data.

## Positive-only semantics

`NIIRunAuditPhysicalAdapterProductionPromotionService.authorize()` fails closed.
It emits an immutable
`NIIRunAuditPhysicalAdapterProductionPromotionAuthorization` only when:

- the Phase 39 assessment is `READY`;
- the authorization reference is present;
- every required governance-evidence category is represented exactly once; and
- the resulting evidence tuple can be canonicalized deterministically.

A blocked Phase 39 assessment, incomplete evidence, duplicate evidence, or a
blank authorization reference raises a domain-specific error. There is no
"partially authorized" state.

## Determinism and auditability

Evidence is canonicalized by requirement value and source reference before the
authorization is constructed. The authorization object validates that:

- the readiness assessment remains `READY`;
- all required evidence categories are present;
- no evidence category is duplicated; and
- evidence ordering is canonical.

The authorization exposes adapter and environment references through the Phase 39
assessment, preserving one chain of identity:

Phase 38 technical certification → Phase 39 production readiness → Phase 40
promotion authorization.

## Explicitly not implemented

Phase 40 does not add or execute:

- PostgreSQL or any other database;
- SQLAlchemy, ORM mappings, or Alembic migrations;
- DSNs, credentials, secrets, tokens, or certificates;
- infrastructure provisioning;
- deployment pipelines or deployment execution;
- runtime dependency injection or startup wiring;
- human approval workflow execution;
- REST, API, or UI integration; or
- any external integration blocked by Issue #66.

## Architectural boundary

A Phase 40 authorization means only that the domain has immutable proof that the
specified `READY` candidate has the required governance authorization references.
A future slice may consume that authorization to define a deployment plan or
activation boundary, but such a slice must remain separate from this gate and
must preserve exact adapter, environment, schema, codec, integrity, and repository
identity.
