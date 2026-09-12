# IRRBB Phase 23 — NII Projection Readiness Certification

## Purpose

Phase 23 introduces a source-neutral certification boundary between canonical banking-book positions and the Phase 22 NII projection strategies.

The objective is not to calculate NII and not to invent missing contractual terms. The objective is to answer one auditable question before a strategy is allowed to project:

> Does this position satisfy the exact evidence requirements declared by the approved NII strategy profile?

This phase is intentionally independent from the existing EVE-oriented `IRRBBPositionDataQualityService`. EVE and NII may require different contractual fields, schedules, market inputs, behavioral assumptions and replacement policies.

## Core contracts

### `NIIProjectionEvidenceKey`

Stable evidence vocabulary covering two separate categories:

1. canonical position evidence, such as maturity, contractual rate, reference rate, spread, repricing dates/frequency, payment frequency and classified instrument/payment structure;
2. approved external capabilities, such as explicit contractual schedules, forward curves, behavioral earnings models, optionality models, replacement policies and day-count/business-day conventions.

The distinction is enforced. External capability evidence cannot impersonate a missing contractual field.

### `NIIProjectionEvidenceAlternative`

One all-of set of evidence keys.

### `NIIProjectionRequirement`

One named strategy requirement. A requirement is satisfied when **any** declared alternative is complete.

This permits a strategy to declare legitimate alternatives without the domain core selecting one. For example, a future floating-rate strategy may state that its rate basis can be evidenced by either:

- current contractual rate; or
- reference-rate identifier plus contractual spread.

Phase 23 does not declare that policy itself. It only provides the mechanism for an approved profile to express it.

### `NIIProjectionRequirementProfile`

Versioned strategy-owned evidence declaration containing:

- exact `strategy_reference`;
- exact governance `source_reference`;
- explicit `INCLUDED` or `EXCLUDED` scope status;
- zero or more named evidence requirements;
- mandatory exclusion reason when excluded.

Duplicate requirement identifiers and duplicate alternatives are rejected.

### `NIIProjectionCapabilityEvidence`

Represents one approved non-position capability and its source reference.

Examples may include a certified contractual schedule provider, an approved forward-rate curve or an approved replacement-policy parameter set. Phase 23 does not provide or configure any of them.

### `NIIProjectionReadinessAssessment`

Returns exactly one of:

- `READY`: every declared requirement is satisfied;
- `BLOCKED`: one or more declared requirements are unsatisfied;
- `EXCLUDED`: the approved strategy profile explicitly excludes the position from the NII measurement perimeter.

For a blocked position, each finding exposes the missing keys for every permitted alternative. No default is manufactured.

## Readiness algorithm

`NIIProjectionReadinessService.assess(...)` performs the following deterministic sequence:

1. honour an explicit governed exclusion without fabricating requirements;
2. derive only factual evidence already present on the canonical `BankingBookPosition`;
3. add only explicitly supplied approved capability evidence;
4. reject duplicate capability declarations;
5. evaluate every strategy requirement;
6. mark the position `READY` only if every requirement has at least one complete alternative;
7. otherwise return `BLOCKED` with machine-readable missing alternatives.

Decimal zero is valid evidence for numeric contractual fields. Presence checks use `is not None`, never truthiness, where zero is economically meaningful.

`PaymentStructure.OTHER` and `IRRBBInstrumentClass.OTHER` do not count as classified evidence.

## Explicit non-goals

Phase 23 does **not** implement or assume:

- fixed-rate coupon calendars;
- floating-rate reset calendars;
- day-count conventions;
- business-day adjustment conventions;
- forward curves;
- floor/cap valuation rules;
- constant-balance replacement transactions;
- dynamic balance-sheet growth;
- prepayment or early-withdrawal models;
- non-maturity-deposit earnings behavior;
- institutional product-to-strategy mappings;
- physical-source adapters;
- runtime dependency injection;
- UI composition.

These remain separately governed capabilities or future strategy implementations.

## Relationship to Phase 22

Phase 22 established:

`BankingBookPosition -> NIIProjectionStrategy -> NIIPositionProjection -> NIIProjectionBatch`

Phase 23 adds a required certification concept before projection:

`BankingBookPosition + approved requirement profile + approved capability evidence -> NIIProjectionReadinessAssessment`

Only a `READY` assessment is evidence that the declared strategy prerequisites are complete. Phase 23 deliberately does not yet wire this assessment into runtime strategy execution because institutional strategy/profile resolution has not been approved or configured.

## Future integration seam

`NIIProjectionRequirementProfileProvider` is a domain port for resolving the approved requirement profile for one canonical position.

A later application-layer slice may bind:

1. certified canonical position;
2. approved requirement-profile provider;
3. approved capability-evidence providers;
4. readiness service;
5. Phase 22 strategy resolver and projection service.

That orchestration must fail closed if a profile, capability, strategy or position identity is substituted.

## Evidence boundary

Phase 23 does not remove the external source gates already tracked in Issue #66. Borrowings, Power BI semantic models, investment mapping/parity, NMD methodology and other institutional assumptions remain blocked until their evidence is supplied and certified.
