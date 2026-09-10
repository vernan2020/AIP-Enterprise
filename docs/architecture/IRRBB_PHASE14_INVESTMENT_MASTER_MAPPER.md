# IRRBB Phase 14 — Institutional Investment Master Canonical Mapper

## Purpose

Phase 14 introduces the physical anti-corruption mapper for the institutional investment master. Its only responsibility is to transform source evidence that has already crossed the portfolio-master reader into the canonical RTILB/IRRBB position contract without importing dashboard defaults or source-specific assumptions into the domain.

This phase does **not** activate the mapper in `ConfiguredIRRBBComposition`, does not provide a production mapping policy, and does not certify the investment source as production-ready. Phase 12 source certification and the Phase 13 mandatory certification gate remain prerequisites for canonical snapshot assembly.

## Source boundary

The mapper consumes `InvestmentMasterSourcePayload`, which contains:

- the reader's normalized position; and
- the reader's `detected_column_mapping`.

A normalized value is considered native evidence only when the corresponding canonical column is present in `detected_column_mapping` **and** the original value is non-blank in the position's `source_values` map. This deliberately prevents reader/provider convenience defaults from becoming contractual RTILB facts.

The `ConfiguredPortfolioProvider` dashboard payload is explicitly outside this boundary. Its presentation-oriented fallbacks, including zero-valued balances and convenience currency defaults, must not be used as RTILB evidence.

## Versioned mapping policy

`InvestmentMasterCanonicalMappingPolicy` is mandatory when the mapper is constructed. No production default policy exists.

Each `InvestmentMasterMappingRule` explicitly determines, for one approved source product/classification selector:

- canonical instrument class;
- banking-book side;
- payment structure;
- optionality classification; and
- the native field that is authoritative for principal (`principal_balance` or `traded_balance`).

Exact product + classification rules take precedence over an explicitly configured product-level fallback. Unknown source semantics are rejected. The mapper never relies on the defaults of `BankingBookPosition` for instrument class, side-equivalent semantics, payment structure, or optionality.

The resulting `IRRBBPositionSourceRecord.mapping_rule_reference` preserves the exact policy version and selector used to interpret the source record.

`effective_from` is retained as policy governance metadata. This phase does not perform cutoff-policy selection because the mapper receives one record, not the snapshot cutoff. The eventual physical orchestration layer must select and validate the policy applicable to the requested cutoff before activation.

## Fail-closed rules

### Position identity

Canonical `position_id` is allowed only when native evidence supports:

1. contract number + ISIN; or
2. contract number + series.

The institutional reader's row-number fallback is explicitly rejected because row position is not a stable contractual identifier.

### Currency

The institutional reader currently normalizes a missing currency to `CRC` for existing portfolio workflows. Phase 14 does not accept that default as RTILB evidence. A detected currency column and a non-blank native source value are required. Unsupported ISO currency codes are rejected.

### Principal

There is no implicit precedence between `principal_balance` and `traded_balance`. The approved mapping policy selects exactly one authoritative native balance field per source product/classification. If that field is absent or blank, mapping fails; the mapper does not fall back to the other balance and never inserts zero.

This is intentionally stricter than the current dashboard path, whose nominal field can use a presentation-oriented fallback chain.

### Rate type and contractual rate

`variable_rate_flag` is interpreted only through `InvestmentMasterSourceRules.rate_type()`. Unknown or missing flags are rejected.

`nominal_rate` is preserved as supplied by the source. The mapper does not pre-transform percentage units; downstream contractual cash-flow logic already handles the approved rate representation when computing coupon amounts.

Coupon-bearing positions require a supported native periodicity. Unknown periodicities are rejected rather than approximated.

### Floating-rate reset evidence

For floating investments, native contractual `next_repricing_date` and `repricing_frequency_months` are required.

The current institutional master reader does not expose certified native reset fields. Therefore a floating investment from the current reader remains unmappable in Phase 14. A `next_repricing_date` produced elsewhere from the next coupon date or duration logic is **not** accepted as contractual reset evidence, and coupon periodicity is not treated as repricing frequency.

This preserves the Phase 12 finding that floating investment source sufficiency is blocked until contractual reset evidence is demonstrated.

### Optional source fields

`book_value` and `last_interest_payment_date` are mapped only when their native columns and non-blank source values exist. If native evidence is present but malformed, mapping fails explicitly rather than discarding the source value.

## Relationship to source certification

Phase 14 does not bypass source certification. The intended sequence remains:

1. read the physical source;
2. assess source evidence using the Phase 12 requirement profile;
3. obtain an `IRRBBSourceCertificationReport`;
4. apply the Phase 13 certification gate at snapshot assembly; and
5. invoke the canonical mapper only when certification is `READY`.

The mapper is a second defensive boundary. A `READY` source certification does not authorize implicit mappings: every record must still satisfy the mapper's native-evidence and policy rules.

## Scope exclusions

Phase 14 does not:

- compose the investment mapper into runtime;
- create or approve Coopealianza's production product mapping matrix;
- infer contractual reset dates from coupon dates;
- use the ICL aggregate as a contractual position source;
- certify the SQL Server view `VISTA_1514_1515_1516` as a credit or liability contractual source;
- map loans, term deposits, borrowings, non-maturity deposits, or off-balance positions; or
- change EVE, GAP, NII, duration, DV01, VaR, HQLA, or MIL calculation formulas.

Credit and liability source sufficiency therefore remains `NOT_ASSESSED` until an actual granular source schema and contractual-field evidence are demonstrated.

## Activation gate

Production activation of this mapper requires, at minimum:

- an approved, versioned institutional mapping policy covering the actual investment product/classification population;
- proof that the selected policy is effective for the requested cutoff;
- a source certification that is `READY` for the same snapshot;
- explicit resolution of floating-rate reset evidence where applicable; and
- passing CI, security, and parity tests for the physical orchestration layer.

Until those conditions are met, Phase 14 is an isolated canonical mapping capability, not a production RTILB source activation.
