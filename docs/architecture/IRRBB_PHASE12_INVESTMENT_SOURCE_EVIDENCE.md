# IRRBB Phase 12 — Investment Source Evidence Contract

## Status

This document is the governed source reference for the investment RTILB/IRRBB source-requirement profile `RTILB-INVESTMENT-SOURCE`, version `2026.09.10`.

It documents the evidence boundary already implemented in the application and configured-product layers. It does **not** certify a physical source, authorize production activation, infer missing institutional semantics, or replace reconciliation/parity approval.

## Purpose

Investment positions may enter RTILB only after their physical source is shown to satisfy the canonical investment requirements defined in `aip.application.irrbb.investment_source_requirements`.

The current candidate is the institutional portfolio master exposed through `InstitutionalPortfolioMasterReadResult`. The physical workstation/network location remains deployment configuration and is intentionally outside this architecture contract.

The evidence assessor is `InvestmentMasterSourceEvidenceAssessor`. It evaluates source sufficiency only. It does not activate an IRRBB adapter and does not convert uncertified evidence into canonical positions.

## Canonical requirements

The investment source profile contains the following requirements:

| Requirement | Canonical variable | Evidence expectation |
| --- | --- | --- |
| `INV-CUTOFF-DATE` | `cutoff_date` | Valuation cutoff must be traceable to the source snapshot itself. |
| `INV-POSITION-ID` | `position_id` | Stable, reproducible identity across cutoffs. |
| `INV-SOURCE-REFERENCE` | `source_reference` | Auditable source lineage. |
| `INV-PRODUCT-TYPE` | `product_type` | Institutional product identity. |
| `INV-INSTRUMENT-CLASS` | `instrument_class` | Approved deterministic instrument-class mapping. |
| `INV-SIDE` | `side` | Approved deterministic balance-sheet-side mapping. |
| `INV-CURRENCY` | `currency` | Explicit contractual currency; no silent default. |
| `INV-PRINCIPAL` | `principal` | Outstanding contractual principal or nominal. |
| `INV-CARRYING-AMOUNT` | `carrying_amount` | Carrying amount for source/accounting reconciliation. |
| `INV-RATE-TYPE` | `rate_type` | Explicitly classifiable fixed/floating behavior. |
| `INV-CONTRACTUAL-RATE` | `contractual_rate` | Current contractual/facial rate when required. |
| `INV-MATURITY-DATE` | `maturity_date` | Contractual maturity for term investments. |
| `INV-NEXT-REPRICING-DATE` | `next_repricing_date` | Contractual next reset date for floating positions. |
| `INV-REPRICING-FREQUENCY` | `repricing_frequency_months` | Contractual repricing frequency for floating positions. |
| `INV-PAYMENT-FREQUENCY` | `payment_frequency_months` | Coupon/payment frequency or explicit schedule. |
| `INV-PAYMENT-STRUCTURE` | `payment_structure` | Explicit payment-structure classification. |
| `INV-CONTRACTUAL-SCHEDULE` | `contractual_cashflow_schedule` | Source-provided or deterministically derivable contractual cash flows. |
| `INV-OPTIONALITY` | `optionality` | Explicit classification of material embedded optionality. |

## Existing evidence-backed rules

The configured assessor is deliberately conservative:

- A reader `valuation_date` is not, by itself, proof that the valuation cutoff is native to the workbook. `INV-CUTOFF-DATE` therefore remains unassessed until source-native cutoff/selection provenance is demonstrated.
- Stable position identity may be derived only from contract number plus ISIN, or contract number plus series. Row number is not an acceptable cross-cutoff identity.
- Source-file lineage may support `INV-SOURCE-REFERENCE`, but lineage metadata does not certify business semantics.
- Product type, currency, carrying amount, contractual rate and maturity are native only when the corresponding source columns are actually detected.
- Missing currency must not be defaulted to CRC for RTILB certification.
- Principal evidence may come from detected outstanding principal or traded nominal balance. Missing amounts remain missing; dashboard zero defaults are not source evidence.
- Fixed/floating classification uses only the strict explicit variable-rate flag mapping implemented by `InvestmentMasterSourceRules`. Unknown values are not guessed.
- Coupon periodicity may support payment-frequency derivation only through the documented strict mapping. Unsupported values remain unresolved.
- For floating positions, next contractual repricing date and repricing frequency remain blocking unless governed contractual evidence is supplied. A next-coupon proxy or coupon periodicity is not automatically equivalent to contractual repricing semantics.
- Payment structure and optionality remain unassessed until approved source fields or effective-dated institutional mappings are supplied.
- Contractual cash-flow schedule may be classified as derivable only when the existing cash-flow builder prerequisites are evidenced. That derivation does not certify missing floating-rate reset semantics.

These rules are source-certification rules, not valuation assumptions.

## Certification states

The application source-certification service can classify a candidate as `READY`, `INCOMPLETE`, or `BLOCKED`.

`READY` means only that the versioned requirement profile has no blocking or unassessed requirements under the supplied evidence. It is **not** equivalent to production activation authorization.

A production investment adapter must remain fail-closed until all additional governance gates are satisfied, including source certification, approved effective-dated classification policies, source-selection/cutoff provenance, rejected-row completeness policy, reconciliation to the governed source/accounting perimeter, calculation readiness, and institutional benchmark/parity approval.

## Evidence still required before production activation

The current architecture intentionally leaves unresolved any fact that is not proven by governed evidence. In particular, production activation requires evidence sufficient to establish, where applicable:

1. source-native valuation cutoff and deterministic source-selection provenance;
2. effective-dated product and classification policy;
3. instrument class and banking-book side mapping;
4. contractual payment structure and principal semantics;
5. explicit optionality treatment;
6. contractual reset date and reset frequency for floating-rate positions;
7. rejected-row/completeness policy and source reconciliation;
8. applicability of the approved policy to the requested cutoff; and
9. institutional calculation/parity benchmark acceptance.

No code path may satisfy these gates by defaulting, guessing, copying dashboard presentation defaults, or substituting a proxy that has not been explicitly approved for RTILB.

## Data and security boundary

This repository must not contain contractual position rows, balances, credentials, tokens, secrets, or workstation-specific paths as evidence. Evidence committed to the repository should be limited to reviewed contracts, deterministic rules, tests and non-sensitive metadata needed to prove behavior.

Physical-source activation is a separate controlled step after the evidence and certification gates above are satisfied.
