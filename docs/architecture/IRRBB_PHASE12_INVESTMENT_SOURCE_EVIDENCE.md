# IRRBB / RTILB — Phase 12 Investment Source Evidence

## 1. Purpose

Phase 12 evaluates the first real institutional candidate source against the source-certification contract introduced in Phase 11.

The candidate is the institutional investment master already read by `InstitutionalPortfolioMasterReader`.

This phase is an **evidence and sufficiency assessment only**. It does not compose the investment master into the IRRBB runtime, does not alter EVE/GAP calculations and does not approve any physical source for credit or liabilities.

## 2. Architectural boundary

```text
Institutional investment master workbook
        |
        v
InstitutionalPortfolioMasterReader
        |
        | normalized rows + detected column mapping + lineage
        v
InvestmentMasterSourceEvidenceAssessor
        |
        +--> InvestmentMasterSourceRules
        |
        v
IRRBBSourceCertificationService
        |
        v
READY / INCOMPLETE / BLOCKED
```

The assessor consumes the reader result directly. It intentionally does **not** consume `ConfiguredPortfolioProvider` dashboard positions because that provider materializes convenience defaults such as `0.0` for some missing numeric fields. Those defaults are acceptable for presentation-oriented portfolio payloads but cannot cross the RTILB canonical boundary as evidence of contractual data.

## 3. Fail-closed rules

Phase 12 applies the following invariants:

- A missing source value is never certified because another layer later defaults it to zero.
- Currency is not assumed to be CRC when the source column is absent.
- Stable position identity never uses workbook row number as the cross-cutoff identifier.
- `RateType` is derived only from an explicit finite mapping of the institutional variable-rate flag.
- Payment frequency is derived only from an explicit supported periodicity mapping.
- The existing `PortfolioContractualCashFlowService` may support deterministic investment schedule construction only when its source prerequisites are evidenced.
- The current duration rule that derives the next coupon date is **not** certified as a contractual next repricing/reset date.
- Coupon periodicity is **not** certified as repricing frequency unless a separate approved contractual rule establishes equivalence.
- Absence of optionality data is not interpreted as `OptionalityType.NONE`.
- `INCOMPLETE` and `BLOCKED` are valid and expected outcomes. A candidate is not promoted to `READY` for convenience.

## 4. Candidate evidence matrix

The matrix below describes what the current institutional master can prove through the existing reader contract. Runtime certification remains snapshot-dependent because detected columns and accepted row values are evaluated at execution time.

| RTILB requirement | Institutional master evidence | Phase 12 treatment |
|---|---|---|
| `cutoff_date` | Reader exposes `valuation_date`, but it can be supplied/overridden by adapter context | `NOT_ASSESSED` until workbook-native cutoff provenance is proven |
| `position_id` | `contract_number` plus `isin` or `series` | `DERIVABLE_WITH_DOCUMENTED_RULE` only when every accepted row produces a unique stable identity |
| `source_reference` | Reader `source_file` metadata | `AVAILABLE_FROM_SUPPLEMENTARY_SOURCE` |
| `product_type` | `product_code` column | `NATIVE_AVAILABLE` when detected |
| `instrument_class` | No approved RTILB product mapping yet | `NOT_ASSESSED` |
| `side` | No approved source classification rule yet | `NOT_ASSESSED` |
| `currency` | `currency` column | `NATIVE_AVAILABLE`; missing column is `MISSING_BLOCKING_EVE` |
| `principal` | `principal_balance` and/or `traded_balance` | `NATIVE_AVAILABLE`; no zero substitution |
| `carrying_amount` | `book_value` | `NATIVE_AVAILABLE` when detected |
| `rate_type` | `variable_rate_flag` | `DERIVABLE_WITH_DOCUMENTED_RULE` only for strict approved flags |
| `contractual_rate` | `nominal_rate` | `NATIVE_AVAILABLE` when detected |
| `maturity_date` | `maturity_date` | `NATIVE_AVAILABLE`; missing column is `MISSING_BLOCKING_EVE` |
| `next_repricing_date` | No certified native reset field | Fixed-only snapshot: `NOT_APPLICABLE`; floating snapshot: `MISSING_BLOCKING_EVE` |
| `repricing_frequency_months` | Coupon periodicity exists but equivalence to reset frequency is not approved | Fixed-only snapshot: `NOT_APPLICABLE`; floating snapshot: `MISSING_BLOCKING_EVE` |
| `payment_frequency_months` | `periodicity` | `DERIVABLE_WITH_DOCUMENTED_RULE` for supported coupon-bearing rows |
| `payment_structure` | No approved native field or product mapping | `NOT_ASSESSED` |
| contractual cash-flow schedule | Principal/nominal, maturity, coupon rate, periodicity and last-payment date feed existing contractual service | `DERIVABLE_WITH_DOCUMENTED_RULE` only when all required row-level inputs are sufficient |
| `optionality` | No certified optionality field | `NOT_ASSESSED` |

## 5. Derivation contracts

### 5.1 Stable position identity

Rule reference: `RULE:INVESTMENT-POSITION-ID:2026.09.10`.

Permitted identities:

- `contract:<contract_number>|isin:<isin>`
- `contract:<contract_number>|series:<series>`

The rule returns no identity when the contract component is absent. Row number is deliberately excluded because it is not stable across cutoffs.

### 5.2 Rate type

Rule reference: `RULE:INVESTMENT-RATE-TYPE:2026.09.10`.

Only explicit recognized fixed/floating source flags are mapped. Unknown, blank or unsupported values return `None` and therefore cannot be certified as available.

### 5.3 Payment frequency

Rule reference: `RULE:INVESTMENT-PAYMENT-FREQUENCY:2026.09.10`.

Only supported institutional periodicities are mapped to months. Unsupported periodicities remain unresolved.

### 5.4 Contractual investment schedule

Rule reference: `aip.domain.portfolio.services.PortfolioContractualCashFlowService`.

The existing service can construct principal flows and supported coupon schedules from normalized investment terms. For variable-rate securities, future coupon amounts generated at the current nominal rate retain projected-current-rate semantics. Phase 12 does not treat those projected coupons as proof of a scenario-aware repricing model.

## 6. Known source gaps after Phase 12

The current investment master is useful but **not yet a self-sufficient RTILB source**. Before production composition, the following must be resolved with evidence and approved rules as applicable:

- workbook-native cutoff provenance;
- canonical instrument-class mapping;
- balance-sheet side mapping;
- payment-structure mapping;
- explicit optionality classification;
- contractual next-reset date for floating positions;
- contractual repricing frequency for floating positions;
- common EVE dependencies outside this investment-position profile, including approved curves, FX conversion and Tier 1 capital, through their own certified source profiles.

## 7. ICL is not a liability-position substitute

`InstitutionalICLReader` exposes regulatory liquidity aggregates such as ICL, liquid-asset fund, total 30-day inflows/outflows and net cash outflow. It does not expose the position-level contractual identifiers, balances, rates, maturities or repricing terms required by the RTILB banking-book contract.

Therefore Phase 12 explicitly leaves the ICL source in the liquidity perimeter. It is not promoted as a liability/captations source for RTILB.

## 8. Completion gate

Phase 12 is complete only when:

1. the investment requirement profile is versioned and remains canonical rather than workbook-specific;
2. the evidence assessor reports only claims supported by detected columns and accepted source rows;
3. source rules return unresolved values rather than implicit defaults;
4. unit tests prove fixed, floating, missing-column, unknown-flag and unstable-ID behavior;
5. no investment source is wired into the runtime composition;
6. CI and Security pass on the exact pull-request head SHA.

Only after this gate may a later phase consider implementing an actual `IRRBBCanonicalPositionMapper` for the investment master, and even then production composition must remain blocked until all mandatory source-certification requirements are satisfied.