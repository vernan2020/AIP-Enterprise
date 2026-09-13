# IRRBB Phase 61 — NII Audit Post-Recovery Operational Recovery Authorization Gate

## Purpose

Phase 61 authorizes a second governed return-to-service action after a successful post-recovery intervention has been accepted by Phase 60.

The first recovery lifecycle is retained as historical evidence through Phase 53–55. After Phase 56 created a distinct continuity epoch, Phase 57 re-attested its operational status, Phase 58 authorized a new intervention, Phase 59 recorded its externally reported execution, and Phase 60 accepted that intervention. Phase 61 therefore requires a new recovery authorization identity rather than reusing the authorization from the first recovery lifecycle.

## Composition boundary

`NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorization` retains the exact `NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalInterventionAcceptance` by identity.

The retained chain remains traceable as:

`Previous Steady State -> Prior Intervention -> Prior Recovery -> Recovery Acceptance -> Continuity Epoch -> Status Re-Attestation -> New Intervention -> New Intervention Acceptance -> New Recovery Authorization`

No upstream aggregate is copied, reconstructed, mutated, or promoted into new authority outside its lifecycle.

## Reused recovery vocabulary

Phase 61 deliberately reuses the Phase 53 recovery action and evidence vocabulary.

Recovery actions:

- `RESUME`
- `REACTIVATE`

Required evidence controls:

1. `INTERVENTION_ACCEPTANCE_VERIFIED`
2. `RECOVERY_POLICY_VERIFIED`
3. `RECOVERY_READINESS_CONFIRMED`
4. `OPERATIONS_RECOVERY_AUTHORITY_CONFIRMED`
5. `CONTINUITY_PROTECTION_CONFIRMED`

Each evidence item carries a nonblank opaque `source_reference`.

## Exact action pairing

The accepted Phase 58 intervention action determines the only valid recovery action:

- accepted `SUSPEND` -> `RESUME`
- accepted `DEACTIVATE` -> `REACTIVATE`

A mismatched action fails closed.

Phase 61 does not infer or execute the action. The caller supplies the action explicitly and the domain validates the pairing.

## Recovery-cycle separation

A Phase 61 authorization requires a nonblank new `authorization_reference`.

That reference must be different from the `recovery_authorization_reference` retained from the first recovery lifecycle. Reusing the previous recovery authorization identity is rejected.

This prevents an earlier return-to-service authority from being replayed as authority for the post-recovery intervention cycle.

## Evidence rules

The authorization requires exactly one evidence item for every existing Phase 53 recovery control.

Duplicate, missing, unexpected, or noncanonical evidence is rejected. Evidence is canonicalized by `(requirement.value, source_reference)` before construction by the service.

## Service behavior

`NIIRunAuditPhysicalAdapterProductionPostRecoveryOperationalRecoveryAuthorizationService.authorize(...)`:

1. requires one exact Phase 60 intervention acceptance;
2. validates a nonblank new recovery authorization reference;
3. rejects reuse of the prior recovery authorization reference;
4. validates exact `SUSPEND -> RESUME` / `DEACTIVATE -> REACTIVATE` pairing;
5. rejects duplicate recovery evidence;
6. rejects missing or unexpected recovery controls;
7. canonicalizes evidence order;
8. returns one immutable positive-only authorization.

The service has no side effects.

## Explicit non-goals

Phase 61 does **not** implement:

- `RESUME` or `REACTIVATE` execution;
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
- deployment or rollback execution;
- PostgreSQL, database, SQLAlchemy, ORM, or Alembic operations;
- DSNs, credentials, tokens, certificates, or secrets;
- shell, PowerShell, SQL, or operating-system commands;
- network connectivity;
- infrastructure provisioning;
- CI/CD operational recovery jobs;
- REST, API, or UI integration;
- external integrations;
- any workaround for blocked Issue #66.

## Security invariant

Possession of a Phase 61 authorization proves only that one exact Phase 60 acceptance has a complete, canonical, source-neutral recovery authorization evidence set, a valid intervention-to-recovery action pairing, and a recovery authorization identity distinct from the previous lifecycle.

It does not prove that AIP executed recovery, changed runtime state, started services, queried monitoring, verified infrastructure, or independently established the external evidence.

## Next safe boundary

A subsequent phase may introduce a post-recovery **Operational Recovery Execution Receipt Contract**, observational only, bound to one exact Phase 61 authorization. It should reuse the existing recovery checkpoint/status vocabulary, record externally reported `RESUME` or `REACTIVATE` outcomes, derive overall success deterministically, and perform no runtime, provider, monitoring, or infrastructure actions.
