# IRRBB / RTILB — SUGEF data requirements matrix

## 1. Purpose

This document defines the **source-independent data contract** required by AIP Enterprise to reproduce the SUGEF supervisory workbook titled **“Método estándar para medir el riesgo de tasa de interés en el libro bancario”** and to reuse the same normalized information in the VEP / Delta EVE engine.

The physical source is deliberately undefined. The contract may later be populated from SQL Server, regulatory XML, OneDrive/Excel, PostgreSQL, APIs, or a combination of these.

The matrix distinguishes:

- `NATIVE`: value should come directly from a legitimate source record;
- `DERIVED`: AIP may derive it deterministically from complete native fields;
- `MARKET`: external market/reference input, e.g. BCCR FX;
- `BEHAVIORAL`: approved behavioral assumption, not inferred from contract data;
- `MAPPING_PENDING`: the supplied workbook does not uniquely determine the mapping.

No missing value is silently imputed.

## 2. Global supervisory requirements

| Field | Status | GAP use | VEP / Delta EVE use | Notes |
|---|---|---:|---:|---|
| `cutoff_date` | NATIVE | Yes | Yes | Reporting / valuation date. |
| `position_id` | NATIVE | Yes | Yes | Stable identifier for drill-down and reconciliation. |
| `source_system` | NATIVE | Yes | Yes | SQL/XML/Excel/etc. trace. |
| `source_reference` | NATIVE | Yes | Yes | Exact source record / row / operation trace. |
| `accounting_account_code` | NATIVE | Yes | Reconciliation | Required to reconcile the workbook perimeter against accounting families. |
| `banking_book_flag` | NATIVE/DERIVED | Yes | Yes | Must exclude trading-book positions. |
| `trading_book_exclusion_reason` | NATIVE/DERIVED | Yes | Yes | Includes investment-fund participations explicitly excluded by the workbook. |
| `native_currency` | NATIVE | Yes | Yes | Preserve original contractual currency. |
| `supervisory_currency_block` (`MN`/`ME`) | DERIVED | Yes | No | Must be derived from native currency, not from converted CRC amount. |
| `amount_native` | NATIVE | Yes | Yes | Contractual amount in native currency. |
| `reporting_amount_crc` | DERIVED | Yes | Yes | Converted amount for supervisory reporting. |
| `bcrr_sell_fx_month_end` | MARKET | ME | FX conversion | BCCR selling reference FX at month-end. |
| `udes_value_crc_month_end` | MARKET | UD | FX-like conversion | BCCR month-end value for Development Units. |
| `conversion_source` | NATIVE/MARKET | Yes | Yes | Audit trail for FX/UD conversion. |
| `conversion_date` | NATIVE/MARKET | Yes | Yes | Must match applicable month-end rule. |

### Reporting precision

The workbook requests balances in **Costa Rican colones without cents**. AIP should retain full-precision native and CRC amounts internally and round only at the supervisory presentation/export boundary.

## 3. SUGEF row-classification fields

The visible MN/ME templates require enough metadata to route each position into one supervisory row.

| Field | Required for | Status | Notes |
|---|---|---|---|
| `instrument_class` | All | NATIVE/DERIVED | Investment, credit, deposit/borrowing, derivative/off-balance. |
| `balance_sheet_side` | All | DERIVED | Asset / liability / off-balance. |
| `rate_type` | Investments, credit, term liabilities | NATIVE | Fixed vs variable/semivariable. |
| `first_repricing_date` / `next_repricing_date` | Variable/semivariable | NATIVE/DERIVED | First reset date is the operative risk date for semivariable contracts. |
| `counterparty_family` | Liabilities | NATIVE/DERIVED | PUBLIC, BCCR, FINANCIAL_ENTITY, OTHER. |
| `funding_term_type` | Liabilities | NATIVE | SIGHT vs TERM. |
| `has_financial_cost` | Sight liabilities | NATIVE/DERIVED | Required by separate sight rows. |
| `product_type` | All | NATIVE | Source product classification; not used as the only source of risk logic. |

### Visible SUGEF rows

Assets:

1. Portafolio de inversiones, tasa fija
2. Portafolio de inversiones, tasa variable / semivariable
3. Cartera de crédito, tasa fija
4. Cartera de crédito, tasa variable / semivariable

Liabilities, for public / BCCR / financial entities:

- a la vista, con costo financiero;
- a la vista, sin costo financiero;
- a plazo, tasa fija;
- a plazo, tasa variable / semivariable.

The workbook visually enables only the **Overnight** cell for sight-obligation rows; later bands are blocked/greyed. This is treated as the workbook GAP presentation rule. It does **not** replace the separate behavioral treatment required for VEP/EVE non-maturity deposits.

## 4. Investment data contract

### 4.1 Common investment fields

| Field | Fixed | Variable / semivariable | Status | Purpose |
|---|---:|---:|---|---|
| `security_id` / ISIN / series | Yes | Yes | NATIVE | Position identity and market enrichment. |
| `nominal_principal` | Yes | Yes | NATIVE | Principal amount. |
| `current_outstanding_principal` | Yes | Yes | NATIVE | Current notional if amortizing/restricted. |
| `maturity_date` | Yes | Yes | NATIVE | Contractual principal payment date. |
| `contractual_rate` | Yes | Yes | NATIVE | Current contractual coupon/rate. |
| `coupon_frequency` | If coupon-bearing | If coupon-bearing | NATIVE | Schedule generation. |
| `last_coupon_date` | Preferred | Preferred | NATIVE | Exact coupon schedule anchor. |
| `next_coupon_date` | DERIVED/NATIVE | DERIVED/NATIVE | DERIVED/NATIVE | Contractual flow date. |
| `zero_coupon_flag` | If applicable | If applicable | NATIVE/DERIVED | Redemption amount logic. |
| `next_repricing_date` | No | Yes | NATIVE | GAP and scenario projection. |
| `repricing_frequency` | No | Yes | NATIVE | Scenario and future reset sequence. |
| `reference_rate` | No | Preferred | NATIVE | Needed for robust scenario repricing. |
| `spread` | No | Preferred | NATIVE | Needed for robust scenario repricing. |
| `rate_floor` / `rate_cap` | If contractual | If contractual | NATIVE | Optionality / reset constraint. |

### 4.2 GAP rule

- Fixed-rate investments: coupons and principal are assigned by contractual payment date.
- Zero-coupon investments: total redemption amount, including interest paid at maturity, is assigned to the maturity band.
- Variable/semivariable investments: contractual payments through the next reset remain in their own payment bands; residual principal is assigned at repricing. Post-reset current-rate coupons must not be carried forward merely to populate GAP.

AIP already reuses `PortfolioContractualCashFlowService` for the canonical investment schedule; no second investment coupon calendar is permitted.

## 5. Credit data contract

### 5.1 Position-level fields

| Field | Fixed | Variable / semivariable | Status | Purpose |
|---|---:|---:|---|---|
| `loan_id` | Yes | Yes | NATIVE | Stable operation identity. |
| `current_outstanding_principal` | Yes | Yes | NATIVE | Current principal. |
| `origination_date` | Preferred | Preferred | NATIVE | Contract / QA. |
| `maturity_date` | Yes | Yes | NATIVE | Final contractual date. |
| `contractual_rate` | Yes | Yes | NATIVE | Current contract rate. |
| `rate_type` | Yes | Yes | NATIVE | Fixed / variable / semivariable. |
| `next_repricing_date` | No | Yes | NATIVE/DERIVED | Mandatory for variable/semivariable GAP. |
| `repricing_frequency` | No | Yes | NATIVE | Required for scenario projection beyond first reset. |
| `reference_rate` | No | Preferred | NATIVE | TRI/TBP/etc. when applicable. |
| `spread` | No | Preferred | NATIVE | Contract margin. |
| `rate_floor` / `rate_cap` | If contractual | If contractual | NATIVE | Optionality / reset constraints. |
| `payment_frequency` | Yes | Yes | NATIVE | Contractual schedule. |
| `payment_structure` | Yes | Yes | NATIVE | Amortizing/bullet/etc. |
| `prepayment_option` | If contractual | If contractual | NATIVE | Behavioral analysis / EVE. |

### 5.2 Required normalized schedule

The safest contract for credit is one record per contractual payment:

| Field | Status | GAP | VEP/EVE |
|---|---|---:|---:|
| `payment_date` | NATIVE/DERIVED | Yes | Yes |
| `total_installment` | NATIVE/DERIVED | Yes | Yes |
| `principal_component` | NATIVE/DERIVED | Required for floating amortizing | Yes |
| `interest_component` | NATIVE/DERIVED | Useful | Yes |
| `outstanding_principal_after` | NATIVE/DERIVED | Required at/through repricing unless derivable | Useful |
| `flow_type` | DERIVED | Yes | Yes |
| `source_reference` | NATIVE | Yes | Yes |

### 5.3 GAP rule

Fixed credit:

- every remaining installment, including principal and interest, is allocated to its contractual payment band.

Variable / semivariable credit:

- include installments due up to and including the next repricing date;
- determine principal outstanding immediately after the payment at repricing;
- place that residual principal in the repricing band;
- do not include post-reset installments using the current rate.

If the residual principal cannot be obtained from `outstanding_principal_after` or derived from complete principal components, the position is `INCOMPLETE` for SUGEF GAP.

## 6. Liability data contract

### 6.1 Position-level fields

| Field | Sight | Term fixed | Term variable/semi | Status |
|---|---:|---:|---:|---|
| `obligation_id` | Yes | Yes | Yes | NATIVE |
| `counterparty_family` | Yes | Yes | Yes | NATIVE/DERIVED |
| `current_outstanding_principal` | Yes | Yes | Yes | NATIVE |
| `has_financial_cost` | Yes | Not row discriminator | Not row discriminator | NATIVE/DERIVED |
| `maturity_date` | No contractual maturity | Yes | Yes | NATIVE |
| `contractual_rate` | If cost-bearing | Yes | Yes | NATIVE |
| `payment_frequency` | If applicable | Yes | Yes | NATIVE |
| `next_repricing_date` | If applicable | No | Yes | NATIVE |
| `repricing_frequency` | If applicable | No | Yes | NATIVE |
| `reference_rate` / `spread` | If variable | No | Preferred | NATIVE |
| `early_withdrawal_option` | If applicable | If applicable | If applicable | NATIVE |

### 6.2 Sight obligations

For the **SUGEF GAP workbook only**, the visual template provides the Overnight band as the entry location for sight obligations and blocks later bands. A source adapter therefore needs the month-end balance split by:

- counterparty family;
- with / without financial cost;
- MN / ME.

For **VEP/EVE**, the same sight balances must not automatically be given an overnight behavioral maturity. They require a separately approved non-maturity-deposit / behavioral model.

### 6.3 Term liabilities

Fixed-rate term liabilities follow contractual payment dates.

Variable/semivariable term liabilities use the same conceptual reset logic as variable assets: payments through repricing plus residual principal at the reset date, subject to the exact contractual structure.

## 7. Derivatives / off-balance data contract

The workbook instructions require interest-rate hedging derivatives, but the visible MN/ME template does not provide a dedicated derivative row. Therefore the following fields are defined for domain readiness while the final supervisory row is `MAPPING_PENDING`:

- derivative/trade ID;
- hedge designation / purpose;
- pay/receive leg;
- notional;
- currency;
- fixed leg rate;
- floating reference index;
- spread;
- reset frequency;
- next reset date;
- payment frequency;
- maturity;
- contractual cash-flow schedule or sufficient terms to derive it;
- source accounting / off-balance reference.

AIP must not route derivative amounts into another row merely to make the template balance.

## 8. Accounting perimeter and reconciliation

The workbook identifies the following account families.

### Investments

- `122` Investments at fair value through OCI
- `123` Investments at amortized cost
- `124` Financial instruments in default / delinquency / litigation
- `125` Matured and restricted financial instruments
- `128` Accounts/products receivable associated with investments, excluding products associated with defaulted entities

### Credit

- `131` Current loans
- `132` Past-due loans
- `133` Judicial collection loans
- `134` Restricted loans
- `136` Direct incremental costs associated with loans
- `137` Deferred income — credit portfolio
- `138` Accounts/products receivable associated with credit, excluding products associated with judicial collection loans

### Public obligations

- `211` Sight deposits
- `213` Term deposits
- `219` Charges payable associated only with account `213`

### BCCR obligations

- `221` Sight obligations with BCCR
- `222` Term obligations with BCCR
- `228` Charges payable associated only with account `222`

### Financial / non-financial entity obligations

- `231` Sight obligations with financial entities
- `232` Term obligations with financial entities
- `233` Obligations with non-financial entities
- `238` Charges payable associated with accounts `232` and `233`

These account families are a **reconciliation perimeter**, not a replacement for operation-level contractual cash flows.

A future adapter should produce, per family:

```text
accounting_balance_crc
- excluded_non_banking_book_crc
- excluded_by_explicit_template_rule_crc
= expected_irrb_gap_perimeter_crc

vs

sum(normalized_irrb_positions_or_flows_crc)
= modeled_irrb_gap_perimeter_crc
```

with an explicit difference and drill-down.

## 9. Mapping issues that remain open

### 9.1 Account 233

The instructions include account `233 — Obligaciones con entidades no financieras`, but the visible template only has rows labelled **obligaciones con entidades financieras**. This mapping is not uniquely determined by the workbook and is therefore `MAPPING_PENDING`.

### 9.2 Derivatives

The instructions require interest-rate hedging derivatives, but no explicit visible row is provided. Supervisory row placement remains `MAPPING_PENDING`.

### 9.3 Behavioral assumptions

The “Preguntas adicionales” sheet asks about policies and analyses for loan prepayments and early cancellation of obligations. It does not provide quantitative behavioral parameters. These inputs remain `BEHAVIORAL` and require an approved methodology before use in VEP/EVE.

## 10. Minimum source interfaces

Regardless of storage technology, a source implementation should be able to populate the equivalent of five logical datasets.

### A. `irrbb_position`

One row per banking-book position:

```text
cutoff_date
position_id
source_system
source_reference
accounting_account_code
instrument_class
product_type
balance_sheet_side
counterparty_family
funding_term_type
has_financial_cost
native_currency
current_outstanding_principal
rate_type
contractual_rate
reference_rate
spread
origination_date
maturity_date
next_repricing_date
repricing_frequency
payment_frequency
rate_floor
rate_cap
optionality
banking_book_flag
```

### B. `irrbb_contractual_schedule`

One row per future contractual payment:

```text
position_id
payment_date
total_amount
principal_component
interest_component
outstanding_principal_after
currency
flow_type
source_reference
```

### C. `irrbb_accounting_reconciliation`

```text
cutoff_date
account_code
currency
accounting_balance
included_balance
excluded_balance
exclusion_reason
source_reference
```

### D. `irrbb_market_reference`

```text
valuation_date
currency
bcrr_sell_fx
udes_crc_value
yield_curve_id
yield_curve_tenor
yield_curve_rate
source
version
```

The FX/UD fields are required for the SUGEF GAP presentation; yield curves are needed by VEP/EVE, not by the 19-band GAP itself.

### E. `irrbb_behavioral_assumption`

```text
methodology_version
product_segment
currency
optionality_type
scenario
parameter_name
parameter_value
effective_from
approved_by
source_reference
```

Behavioral assumptions are never populated from missing contractual data by default.

## 11. Source-sufficiency decision rule

When a candidate source is evaluated later (SQL/XML/OneDrive/etc.), every canonical field will be classified as:

- `NATIVE_AVAILABLE`;
- `DERIVABLE_WITH_DOCUMENTED_RULE`;
- `AVAILABLE_FROM_SUPPLEMENTARY_SOURCE`;
- `MISSING_BLOCKING_GAP`;
- `MISSING_BLOCKING_EVE`;
- `NOT_APPLICABLE`.

A source is acceptable for production only when all required GAP fields are available or legitimately derivable and all VEP/EVE-specific missing fields are either supplied by approved market/behavioral sources or explicitly reported as preventing calculation.

## 12. Design consequence

The future source architecture remains:

```text
SQL / XML / OneDrive / Excel / PostgreSQL / API
                     |
                     v
           Source-specific adapter
                     |
          +----------+-----------+
          |                      |
          v                      v
   BankingBookPosition    ContractualSchedule
          |                      |
          +----------+-----------+
                     |
          +----------+-----------+
          |                      |
          v                      v
  SugefStandardGapService   IRRBB EVE Engine
       19 bands             curves / scenarios
          |                      |
          v                      v
    MN / ME template      VEP / Delta EVE
```

The database choice can therefore be made later without changing the calculation domain.