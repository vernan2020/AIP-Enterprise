# IRRBB Phase 53 — NII Audit Operational Recovery Authorization

## Purpose

Phase 53 adds the positive-only governance boundary that may authorize one exact return-to-service action after one exact Phase 52 operational-intervention acceptance.

The authorization is source-neutral and immutable. It does not execute recovery, resume, reactivation, startup, provider switching, runtime mutation, health checks, or infrastructure changes.

## Input boundary

The contract composes one exact `NIIRunAuditPhysicalAdapterProductionOperationalInterventionAcceptance` by identity. That preserves the complete chain through intervention authorization, intervention receipt, operational status attestation, steady-state operations, adapter identity, environment identity, and artifact identity.

## Recovery actions

Phase 53 defines two explicit governed actions:

- `RESUME`
- `REACTIVATE`

The action is not caller-arbitrary. The accepted intervention determines the only valid recovery action:

- accepted `SUSPEND` -> authorized `RESUME`
- accepted `DEACTIVATE` -> authorized `REACTIVATE`

Any mismatched pair fails closed.

## Required evidence

Every authorization requires exactly one source reference for each requirement:

1. `INTERVENTION_ACCEPTANCE_VERIFIED`
2. `RECOVERY_POLICY_VERIFIED`
3. `RECOVERY_READINESS_CONFIRMED`
4. `OPERATIONS_RECOVERY_AUTHORITY_CONFIRMED`
5. `CONTINUITY_PROTECTION_CONFIRMED`

Duplicate, missing, unexpected, blank, or noncanonical evidence is rejected.

## Positive-only semantics

Existence of `NIIRunAuditPhysicalAdapterProductionOperationalRecoveryAuthorization` means only that the domain accepted a complete evidence set for one exact return-to-service action bound to one exact Phase 52 acceptance.

It does not mean that AIP executed or observed recovery.

## Explicit non-goals

Phase 53 does not implement:

- resume execution
- reactivation execution
- runtime activation or deactivation
- suspension or intervention execution
- process/service/container start, stop, or restart
- dependency-injection or provider mutation
- configuration/environment mutation
- health-check execution
- observability or monitoring calls
- recovery verification
- deployment or rollback execution
- PostgreSQL or database access
- SQLAlchemy or Alembic
- DSNs, credentials, tokens, certificates, or secrets
- shell, PowerShell, SQL, or OS commands
- infrastructure provisioning
- CI/CD recovery jobs
- REST/API/UI integration
- external integrations
- any workaround for Issue #66

## Security invariant

Possession of a Phase 53 authorization proves only that one exact accepted operational intervention has a complete, canonical, source-neutral authorization record for its corresponding return-to-service action. It does not prove that the action was executed, succeeded, or restored production service.

## Next boundary

A later phase may model an operational recovery execution receipt. Such a receipt must remain observational: it may record outcomes reported by an external executor, but the domain must not perform recovery itself.
