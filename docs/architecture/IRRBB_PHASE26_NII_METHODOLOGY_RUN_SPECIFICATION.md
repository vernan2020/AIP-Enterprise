# IRRBB Phase 26 — NII Methodology Run Specification

## Objective

Phase 26 introduces an immutable, source-neutral governance contract for one Delta NII methodology run. Its purpose is to ensure that a completed NII result remains bound to the exact methodology perimeter that requested it.

The phase does **not** introduce new financial assumptions. It packages assumptions that must already be explicit before execution.

## Architecture

The flow is:

`NIIMethodologyRunSpecification`
→ `NIIMethodologyRunService`
→ `NIIScenarioSetEvaluationService`
→ Phase 24 certification per scenario
→ NII per scenario
→ `DeltaNIIService`
→ `NIIMethodologyRunResult`

`NIIMethodologyRunSpecification` composes the existing `NIIProjectionBasis` rather than duplicating its fields. This prevents independent copies of methodology, valuation date, horizon, balance-sheet assumption or shock timing from diverging.

## Specification contract

A run specification contains:

- `run_reference`: explicit auditable identity for the requested run;
- `basis`: the existing `NIIProjectionBasis`, which already carries:
  - versioned methodology profile;
  - valuation date;
  - horizon end date;
  - balance-sheet assumption;
  - shock timing;
  - basis source reference;
- `reporting_currency`;
- `stressed_scenarios`: explicit, ordered, non-empty stress set;
- `policy_references`: explicit, non-empty governance references;
- `evidence_references`: explicit, non-empty evidence/input references.

The specification rejects:

- blank run references;
- empty stress sets;
- `BASE` inside the stressed-scenario set;
- duplicate stressed scenarios;
- missing, blank or duplicate policy references;
- missing, blank or duplicate evidence references.

No default stress set is supplied.

## Result binding

`NIIMethodologyRunResult` contains the original specification and the resulting `NIIScenarioSetEvaluationResult`.

It fails closed if the evaluation substitutes any of these run-defining dimensions:

- projection basis;
- reporting currency;
- ordered stressed-scenario set.

This means downstream runtime, API or UI layers can retain one domain object that explains both **what was requested** and **what was calculated**.

## Service behavior

`NIIMethodologyRunService.execute()` receives a complete specification and delegates its exact fields to the Phase 25 scenario-set evaluator.

The service does not:

- select scenarios;
- select Basel, SUGEF or internal defaults;
- derive the projection horizon;
- choose constant/run-off/dynamic balance-sheet assumptions;
- choose shock timing;
- choose reporting currency;
- create policy or evidence references;
- infer source data;
- implement projection mechanics.

## External-source gates

Phase 26 does not cross Issue #66 source gates. The `policy_references` and `evidence_references` fields are audit identifiers supplied by an authorized caller; this phase does not create physical adapters or claim that any institutional source has been certified.

Borrowings, Power BI credit/term-deposit sources and investment-source certification remain governed by their existing evidence gates.

## Deferred work

Phase 26 intentionally does not implement:

1. institutional scenario policy resolution;
2. production run persistence;
3. runtime/API/UI composition;
4. physical source adapters;
5. coupon or reset schedule generation;
6. forward curves;
7. renewal/replacement transactions;
8. NMD behavioral earnings assumptions;
9. future FX methodology;
10. approval workflow or electronic sign-off.

A later composition layer may load an approved specification from institutional configuration, but it must not mutate the specification after the calculation begins.
