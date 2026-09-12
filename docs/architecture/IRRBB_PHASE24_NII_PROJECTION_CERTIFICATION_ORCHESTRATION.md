# IRRBB Phase 24 — NII Projection Certification Orchestration

## Purpose

Phase 24 connects the Phase 22 projection strategy boundary with the Phase 23 readiness/certification boundary without introducing institutional product rules or physical source adapters.

The orchestration sequence is deliberately fail-closed:

1. obtain the approved requirement profile for every canonical banking-book position;
2. obtain explicitly approved external capability evidence only for positions in scope;
3. assess readiness for every position;
4. if any included position is `BLOCKED`, execute no projection strategy;
5. if every position is `EXCLUDED`, return an explicit no-included-positions result;
6. only when all included positions are `READY`, project exactly those positions;
7. verify that every projection preserves position, scenario, projection basis, and the strategy reference approved by the requirement profile.

## New domain result

`NIIProjectionCertificationResult` represents the portfolio-level outcome and has three statuses:

- `PROJECTED`: every included position was READY and exactly those positions were projected;
- `BLOCKED`: at least one included position lacked required evidence and no strategy was executed;
- `NO_INCLUDED_POSITIONS`: every position was explicitly excluded by an approved profile and no projection batch was manufactured.

The result validates that a projected batch has the same scenario and projection basis as the certification request and that each projected `strategy_reference` equals the corresponding readiness assessment `strategy_reference`.

## New port

`NIIProjectionCapabilityEvidenceProvider` supplies approved non-position evidence for one position, requirement profile, projection basis and scenario.

Examples of such evidence include an approved forward reference-rate curve, explicit contractual schedule, behavioral earnings model, day-count convention or balance replacement policy. The port does not infer whether any capability is required; the approved requirement profile owns that decision.

## Orchestrator

`NIIProjectionCertificationService.project_certified(...)` composes:

- `NIIProjectionRequirementProfileProvider`;
- `NIIProjectionCapabilityEvidenceProvider`;
- `NIIProjectionReadinessService`;
- `NIIProjectionStrategyResolver`;
- `NIIProjectionService`.

Readiness is completed for the entire input set before `NIIProjectionService` is invoked. This prevents a portfolio from being partially projected simply because earlier positions happened to be ready before a later blocking position was discovered.

## Fail-closed invariants

- input position IDs must be unique before any provider is called;
- excluded profiles do not request external capabilities;
- a single BLOCKED assessment prevents every strategy invocation;
- projected position IDs must equal the set of READY position IDs exactly;
- projection scenario and projection basis cannot be substituted;
- projection `strategy_reference` must match the approved profile exactly;
- no empty `NIIProjectionBatch` is created for an excluded-only portfolio.

## Explicit non-goals

Phase 24 does **not** implement or authorize:

- institutional product-to-strategy mappings;
- contractual coupon/reset calendars;
- forward-rate construction or interpolation;
- day-count or business-day conventions;
- floor/cap mechanics;
- constant-balance replacement transactions;
- dynamic balance-sheet growth;
- behavioral or optionality earnings models;
- Power BI, workbook, portfolio-master or other physical adapters;
- runtime/UI composition.

Those transitions remain evidence- and governance-gated. In particular, Phase 24 does not cross the external source gates tracked in Issue #66.

## Architectural consequence

The source-neutral NII path is now:

`BankingBookPosition -> RequirementProfile -> CapabilityEvidence -> ReadinessAssessment -> Strategy -> NIIPositionProjection`

with a portfolio-level certification barrier between readiness and strategy execution.
