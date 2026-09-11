# IRRBB Phase 36 — NII Audit Persistence Activation Gate

## Purpose

Phase 36 introduces a source-neutral, fail-closed authorization boundary before any
physical NII audit persistence adapter can be activated.

The gate composes two certifications that already exist:

1. `NIIAuditPersistenceReadinessAssessment`, which proves that one physical adapter
   has evidence for every required persistence capability; and
2. `NIIRunAuditSerializationCompatibilityCertificate`, which proves that one exact
   schema/codec/integrity/migration configuration covers the complete declared
   readable schema perimeter.

Phase 36 does not implement persistence. It only decides whether one explicit
technical configuration has sufficient, mutually consistent evidence to be eligible
for later runtime activation.

## Positive-only authorization

The domain deliberately does not expose an `authorized=False` result. A
`NIIRunAuditPersistenceActivationAuthorization` can exist only after every required
check succeeds.

A failed check raises `NIIRunAuditPersistenceActivationError` and produces no
authorization object.

This keeps downstream composition fail-closed: possession of an authorization object
means the complete gate passed.

## Explicit activation configuration

`NIIRunAuditPersistenceActivationConfiguration` binds the technical identities that
are intended to run together:

- `adapter_reference`
- exact `NIIAuditSchemaEvolutionContract`
- `codec_reference`
- `integrity_reference`
- `source_reference`

The configuration is caller-supplied evidence of the intended runtime composition.
It does not discover, infer, select or instantiate any implementation.

## Authorization invariants

`NIIRunAuditPersistenceActivationService.authorize(...)` requires all of the
following:

1. the persistence readiness assessment is `READY`;
2. the readiness assessment's adapter reference exactly matches the configured
   adapter reference;
3. the Phase 35 certificate's schema contract exactly matches the configured schema
   contract;
4. the Phase 35 certificate's codec reference exactly matches the configured codec
   reference; and
5. the Phase 35 certificate's integrity reference exactly matches the configured
   integrity reference.

No partial match is accepted.

## Why the explicit binding is required

Persistence readiness and serialization compatibility certify different boundaries.
Readiness identifies a physical adapter and its required capabilities, while Phase 35
identifies the serialization configuration and readable schema perimeter. Neither
object alone proves that they are the exact components intended to operate together.

The activation configuration closes that identity gap without introducing a physical
adapter or runtime dependency-injection layer.

## Reused contracts

Phase 36 does not duplicate earlier rules.

- Required persistence capabilities remain defined by
  `REQUIRED_NII_AUDIT_PERSISTENCE_REQUIREMENTS`.
- READY/BLOCKED evaluation remains the responsibility of
  `NIIAuditPersistenceReadinessService`.
- Schema graph validation and unique migration-path semantics remain in Phases 32–34.
- Static serialization compatibility remains the responsibility of
  `NIIRunAuditSerializationCompatibilityService` from Phase 35.

## Non-goals

Phase 36 deliberately does **not** add:

- PostgreSQL or another database implementation;
- SQLAlchemy or ORM models;
- Alembic or another physical schema migration engine;
- physical writes or reads;
- database credentials or connection configuration;
- runtime dependency injection;
- REST, API or UI integration;
- a mandated serialization format;
- a mandated production integrity algorithm;
- source-specific external integrations;
- automatic production activation.

Issue #66 and all external-source evidence gates remain unchanged.

## Activation boundary

The intended sequence is:

```text
physical-adapter evidence
        |
        v
NIIAuditPersistenceReadinessAssessment (READY)
        |
        +-------------------------------+
                                        |
Phase 35 serialization compatibility    |
        |                               |
        v                               v
NIIRunAuditSerializationCompatibilityCertificate
        |                               |
        +---------------+---------------+
                        |
                        v
NIIRunAuditPersistenceActivationConfiguration
                        |
                        v
NIIRunAuditPersistenceActivationService.authorize(...)
                        |
                        v
NIIRunAuditPersistenceActivationAuthorization
```

The authorization is a prerequisite for a future physical/runtime composition slice;
it is not itself persistence or deployment approval.
