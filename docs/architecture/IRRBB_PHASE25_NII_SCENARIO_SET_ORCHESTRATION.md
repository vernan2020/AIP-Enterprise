# IRRBB Phase 25 — NII Scenario-Set Orchestration

## Purpose

Phase 25 composes the source-neutral NII boundaries delivered in Phases 21–24 into an explicit multi-scenario evaluation flow. It does **not** define regulatory scenarios, instrument mechanics, renewal assumptions or physical-source mappings.

The orchestration path is:

`BankingBookPosition`
→ Phase 24 certification for `BASE`
→ Phase 24 certification for each explicitly requested stressed scenario
→ scenario `NetInterestIncomeService`
→ `DeltaNIIService`
→ `NIIScenarioSetEvaluationResult`

## Explicit scenario contract

The caller must provide:

- one implicit `BASE` scenario; and
- a non-empty ordered tuple of stressed scenarios.

The stressed tuple:

- cannot contain `BASE`;
- cannot contain duplicates; and
- is preserved exactly into the final ΔNII assessment order.

No Basel, SUGEF or internal default shock set is selected by this service.

## Portfolio-level fail-closed behavior

Every requested scenario is first passed through `NIIProjectionCertificationService`.

If any scenario is `BLOCKED`:

- the complete scenario-set result is `BLOCKED`;
- no scenario NII results are produced; and
- no ΔNII is produced.

This prevents a partial set of earnings results from being presented as a complete sensitivity measure.

If every scenario is `NO_INCLUDED_POSITIONS`, the result is explicitly `NO_INCLUDED_POSITIONS`. The service does not invent zero-valued earnings.

A mixed state in which some scenarios are projected while another scenario reports an excluded-only portfolio is rejected as inconsistent scope.

## Zero-accrual policy

A Phase 22 strategy may explicitly return `NO_ACCRUAL_IN_HORIZON`. If all projected positions in a scenario therefore flatten to an empty accrual set, Phase 25 fails closed.

It does **not** silently interpret an empty accrual set as `NII = 0`, because that is a methodology decision that has not yet been approved or represented as a domain policy.

## FX boundary

Scenario NII uses the existing `NIIExchangeRateProvider`. The provider remains scenario-aware and accrual-date-aware. Phase 25 does not reuse EVE spot FX or invent a future FX convention.

## Result invariants

`NIIScenarioSetEvaluationResult` verifies:

- stressed scenarios are explicit, unique and exclude `BASE`;
- certifications match exactly `BASE + requested stresses` and use the same projection basis;
- `BLOCKED` results contain no NII or ΔNII;
- excluded-only results contain no NII or ΔNII;
- evaluated results require every certification to be `PROJECTED`;
- scenario NII results match the exact requested scenario order;
- all NII results use the requested basis and reporting currency; and
- ΔNII assessments match the exact stressed-scenario tuple.

## Explicitly outside Phase 25

Phase 25 does not implement:

1. institutional product-to-strategy mapping;
2. physical source adapters;
3. contractual coupon/reset calendars;
4. forward curve construction;
5. day-count or business-day rules;
6. constant-balance replacement transactions;
7. replacement spreads or FTP assumptions;
8. dynamic balance-sheet growth;
9. prepayment or early-withdrawal behavior;
10. NMD earnings behavior;
11. future FX methodology;
12. a Basel/SUGEF default NII scenario set; or
13. runtime/UI composition.

The external evidence gates tracked in Issue #66 remain unchanged.
