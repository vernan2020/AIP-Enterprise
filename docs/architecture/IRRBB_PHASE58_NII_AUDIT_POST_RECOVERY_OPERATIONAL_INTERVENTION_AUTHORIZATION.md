# IRRBB Phase 58 — NII Audit Post-Recovery Operational Intervention Authorization Gate

## Purpose

Phase 58 re-enters the governed operational intervention lifecycle after an accepted recovery and the creation of a distinct Phase 56 continuity epoch.

Phase 50 authorizes intervention against the original Phase 49 steady-state status attestation. After intervention, recovery, recovery acceptance, continuity-epoch creation, and Phase 57 status re-attestation, that original authorization context must not be reused as if it governed the new operational epoch.

Phase 58 therefore creates a new positive-only intervention authorization bound to one exact Phase 57 re-attestation.

## Authorized actions

Phase 58 reuses `NIIRunAuditPhysicalAdapterProductionOperationalInterventionAction` from Phase 50:

- `SUSPEND`
- `DEACTIVATE`

No second intervention-action enum is introduced.

## Composition boundary

`NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorization` retains the exact `NIIRunAuditPhysicalAdapterProductionOperationalStatusReattestation` by identity.

The retained chain remains traceable through:

`Previous Steady State -> Prior Status Attestation -> Prior Intervention -> Recovery -> Recovery Acceptance -> Continuity Epoch -> Status Re-Attestation -> New Intervention Authorization`

Prior aggregates are not copied, mutated, or reconstructed.

## Authorization preconditions

A Phase 58 authorization is valid only when:

- the Phase 57 re-attestation reference is nonblank;
- its status is `DEGRADED` or `UNAVAILABLE`;
- the non-healthy re-attestation carries at least one exception reference;
- the Phase 56 continuity epoch reference is nonblank;
- the continuity epoch reference is distinct from its previous steady-state operations reference;
- the new authorization reference is nonblank;
- the new authorization reference is different from the intervention authorization reference retained from the prior lifecycle.

`HEALTHY` cannot authorize intervention.

The action is always supplied explicitly. Phase 58 does not infer `SUSPEND` or `DEACTIVATE` from the status.

## Required evidence

Exactly one source-neutral evidence item is required for each control:

1. `STATUS_REATTESTATION_VERIFIED`
2. `CONTINUITY_EPOCH_VERIFIED`
3. `INTERVENTION_POLICY_VERIFIED`
4. `OPERATIONAL_APPROVAL_VERIFIED`
5. `CONTINUITY_IMPACT_VERIFIED`

Each evidence item carries a nonblank opaque `source_reference`.

Duplicate, missing, unexpected, or noncanonical evidence is rejected.

## Service behavior

`NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAuthorizationService.authorize(...)`:

1. requires one exact valid Phase 57 operational status re-attestation;
2. rejects `HEALTHY` re-attestations;
3. defensively requires exception evidence for a non-healthy re-attestation;
4. revalidates the distinct Phase 56 continuity epoch identity;
5. rejects reuse of the prior lifecycle intervention authorization reference;
6. validates complete intervention evidence;
7. canonicalizes evidence order;
8. returns one immutable positive-only authorization.

The service has no side effects.

## Distinction from Phase 50

Phase 50 is bound to the original Phase 49 status attestation and belongs to the first steady-state lifecycle.

Phase 58 is bound to the Phase 57 re-attestation of a distinct post-recovery continuity epoch. The Phase 50 authorization remains historical evidence and is exposed through `previous_intervention_authorization_reference`; it is never treated as authorization for the new epoch.

## Explicit non-goals

Phase 58 does **not** implement:

- `SUSPEND` or `DEACTIVATE` execution;
- process, service, application, or container stop/start/restart;
- runtime activation or deactivation;
- dependency-injection or provider switching;
- runtime configuration or environment mutation;
- health-check execution;
- observability or monitoring queries;
- metric collection;
- incident detection or alert acknowledgement;
- incident workflow execution;
- continuity or failover execution;
- recovery execution;
- deployment or rollback execution;
- PostgreSQL, database, SQLAlchemy, ORM, or Alembic operations;
- DSNs, credentials, tokens, certificates, or secrets;
- shell, PowerShell, SQL, or operating-system commands;
- network connectivity;
- infrastructure provisioning;
- CI/CD operational intervention jobs;
- REST, API, or UI integration;
- external integrations;
- any workaround for blocked Issue #66.

## Security invariant

Possession of a Phase 58 authorization proves only that one exact non-healthy Phase 57 re-attestation has a complete, canonical, source-neutral intervention authorization evidence set and that the authorization identity is distinct from the prior lifecycle.

It does not prove that AIP executed an intervention, stopped services, changed runtime state, queried monitoring, or independently verified infrastructure conditions.

## Next safe boundary

A subsequent phase may introduce a post-recovery **Operational Intervention Execution Receipt Contract**, observational only, bound to one exact Phase 58 authorization. It must record externally reported execution outcomes without performing `SUSPEND`, `DEACTIVATE`, runtime mutation, provider switching, or infrastructure actions.
