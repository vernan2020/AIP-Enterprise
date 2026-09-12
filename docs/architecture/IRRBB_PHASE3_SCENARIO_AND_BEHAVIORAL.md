# IRRBB Phase 3 — Scenario repricing and behavioral core

## Purpose

This phase extends the source-agnostic IRRBB domain with the minimum calculation
contracts required to project floating-rate cash flows under stress and to support
non-maturity deposits (NMD) without embedding unapproved behavioral assumptions.

The implementation remains independent from SQL, XML, OneDrive, Excel, PostgreSQL,
PiPCA or any other physical source.

## Floating-rate scenario projection

A future floating coupon cannot be stressed correctly from the current coupon amount
alone. AIP therefore requires an explicit `FloatingRateCouponBasis` containing:

- position identifier;
- contractual reset date;
- payment date;
- reference-rate code;
- notional used for interest calculation;
- approved accrual fraction;
- contractual spread;
- optional floor and cap;
- source trace.

Rates are represented in decimal form: `0.05 = 5%`.

The accrual fraction is supplied by the source/approved schedule. The domain does not
invent ACT/360, ACT/365 or 30/360.

For a stressed scenario:

```text
Projected reference rate = ScenarioReferenceRateProvider(...)
Effective coupon rate     = projected reference + contractual spread
Effective coupon rate     = apply floor/cap when contractually present
Projected interest        = notional × effective coupon rate × accrual fraction
```

The resulting flow is labelled `SCENARIO_PROJECTED`. Principal or already fixed/source-
provided cash flows are preserved.

If a `PROJECTED_CURRENT_RATE` flow has no explicit projection basis, stressed EVE is
blocked. AIP does not infer the missing notional or day-count basis.

## Scenario curves

`ParameterizedScenarioCurveShocker` applies a signed tenor shock supplied by a
`ScenarioTenorShockProvider`:

```text
stressed_rate = base_rate + shock_bp / 10,000
```

The domain does not embed a steepener/flattener interpolation formula.

`ParallelOnlyScenarioTenorShockProvider` is intentionally restrictive. It supports
only:

- PARALLEL_UP  = `+parallel_bp`;
- PARALLEL_DOWN = `-parallel_bp`.

For STEEPENER, FLATTENER, SHORT_UP and SHORT_DOWN it raises an explicit error until a
methodology-specific tenor transformation is supplied and versioned.

This permits the known parallel calibration to be used without misrepresenting the
headline short/long shock magnitudes as a complete regulatory curve formula.

## Non-maturity deposits

The SUGEF GAP workbook visually reports sight obligations in Overnight, but that
presentation rule must not be reused as an EVE behavioral maturity assumption.

For EVE, AIP requires a versioned `NonMaturityDepositProfile` containing explicit
maturity allocations. Each allocation has:

- tenor in calendar months from valuation date;
- weight of current principal.

Controls:

- weights must be in `[0, 1]`;
- tenors cannot be negative;
- tenors must be unique;
- weights must sum exactly to `1`;
- the profile identifies methodology, version, scenario and source reference.

`NonMaturityDepositBehavioralModel` converts an approved profile into auditable
behavioral principal cash flows. It does not derive weights from observed balances by
itself and does not assume Overnight when no profile exists.

Scenario-specific NMD profiles are supported because stability/runoff assumptions may
be different under stress if an approved methodology requires that treatment.

## Still intentionally pending

This phase does **not** invent or finalize:

1. non-parallel SUGEF/Basel curve-shock formulas;
2. market/reference-rate source selection;
3. curve interpolation and discount-factor conventions;
4. credit prepayment assumptions;
5. term-deposit early-withdrawal assumptions;
6. NMD weights/tenors;
7. derivative supervisory-row mapping;
8. account-233 supervisory-row mapping.

These remain configuration/methodology/source concerns and must be resolved with an
approved parameter set or authoritative data dictionary.

## Calculation sequence after this phase

```text
Normalized BankingBookPosition
        |
        +--> contractual schedule / investment schedule
        |             |
        |             v
        |       Base IRRBBCashFlow
        |             |
        |      floating-rate basis
        |             |
        |             v
        |   Scenario cash-flow projector
        |             |
        |             +------> reference-rate scenario provider
        |             |
        |             v
        |      Scenario cash flows
        |
        +--> NMD --> approved behavioral profile --> behavioral cash flows
                      |
                      v
               discount factors
                      |
                      v
                    EVE
                      |
                      v
             Delta EVE / worst loss
```

The SUGEF 19-band GAP path remains separate and continues to use
`SugefStandardGapService`.
