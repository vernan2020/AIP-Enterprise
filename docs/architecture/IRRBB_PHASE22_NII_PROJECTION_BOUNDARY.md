# IRRBB Phase 22 — NII projection strategy boundary

## Purpose

Phase 22 introduces the source-neutral boundary between certified banking-book positions and the explicit `NIIInterestAccrual` contract introduced in Phase 21.

It does **not** implement contractual calendars, replacement transactions, forward curves, behavioral assumptions or source adapters. Instead, it defines how an approved instrument-specific projection strategy plugs into the NII pipeline and how its output is validated before aggregation.

The objective is to prevent orchestration code from becoming a second source of financial assumptions.

## Architecture

```text
Certified BankingBookPosition
          |
          v
NIIProjectionStrategyResolver
          |
          v
 approved instrument strategy
          |
          v
NIIPositionProjection
          |
          v
NIIProjectionService
          |
          v
NIIProjectionBatch.accruals
          |
          v
NetInterestIncomeService
          |
          v
DeltaNIIService
```

## Strategy port

`NIIProjectionStrategy` receives exactly:

- one canonical `BankingBookPosition`;
- one explicit `NIIProjectionBasis`; and
- one `IRRBBScenario`.

It returns one `NIIPositionProjection`.

Instrument-specific implementations may depend on approved schedule, repricing, curve, optionality or replacement-policy ports, but those dependencies belong inside the strategy implementation. The generic orchestrator does not infer any of them.

`NIIProjectionStrategyResolver` selects the approved strategy from the canonical position. Phase 22 does not implement a concrete resolver because source/product policy has not yet been certified for all institutional instruments.

## Explicit position outcome

A strategy cannot return an unexplained empty tuple.

`NIIPositionProjectionStatus` has two states:

- `PROJECTED`: at least one explicit accrual must be present;
- `NO_ACCRUAL_IN_HORIZON`: no accrual may be present.

This distinction makes a legitimate zero-activity position auditable and prevents missing projection logic from masquerading as a zero result.

The position projection also records a nonblank `strategy_reference`, which must identify the approved/versioned strategy or policy basis used by the implementation.

## Fail-closed invariants

`NIIPositionProjection` rejects:

- blank position or strategy references;
- `PROJECTED` results without accruals;
- `NO_ACCRUAL_IN_HORIZON` results that contain accruals;
- duplicate accrual IDs within one position;
- accruals assigned to another position;
- accruals assigned to another scenario;
- accruals starting before the projection valuation date;
- accruals ending after the projection horizon.

`NIIProjectionBatch` additionally rejects:

- an empty position set;
- duplicate position IDs;
- position projections using another scenario;
- position projections using another projection basis;
- duplicate accrual IDs across different positions.

The flattened `accruals` property contains only explicit accruals. It does not manufacture zero-value records for `NO_ACCRUAL_IN_HORIZON` positions.

## Orchestration control

`NIIProjectionService` resolves exactly one strategy per supplied position and then validates that the returned projection did not substitute:

- `position_id`;
- scenario; or
- projection basis.

This mirrors the exact-source-binding discipline already used by the source-integration layers: a valid strategy must not be able to return a projection for a different business object than the caller requested.

## Deliberately not implemented

Phase 22 does not decide or implement:

1. fixed-rate contractual accrual calendars;
2. floating-rate reset calculations;
3. forward reference-rate curves;
4. spread, floor or cap application;
5. constant-balance-sheet replacement transactions;
6. replacement margins or FTP assumptions;
7. dynamic-plan growth;
8. prepayment or early-withdrawal behavior;
9. NMD earnings behavior;
10. FX forecasting;
11. instrument-to-strategy institutional mapping;
12. physical source adapters;
13. runtime or UI composition.

All such behavior remains separately versioned and evidence-backed.

## Next safe implementation slices

The next code slices should be instrument-specific and should begin only where contractual evidence is already sufficient. A fixed-rate strategy may be implemented once its schedule/day-count/payment semantics are explicitly governed. Floating-rate, behavioral, replacement and source-specific strategies remain blocked until their required evidence and methodology are available.

Phase 22 therefore creates the plug-in seam without pretending that the missing institutional assumptions have already been approved.
