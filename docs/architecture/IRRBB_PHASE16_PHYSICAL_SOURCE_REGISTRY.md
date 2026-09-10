# IRRBB Phase 16 — Governed physical source registry

## Purpose

Phase 16 records the institutionally designated physical source candidate for each RTILB position
segment before any new physical adapter is allowed to feed the canonical IRRBB boundary.

The registry answers **where a segment is expected to come from**. It does not answer whether that
source contains every contractual field required by GAP, EVE or scenario repricing. Field-level
readiness remains exclusively governed by the Phase 11 source-certification contracts and the
certification gate introduced in the subsequent source ACL flow.

## Institutional source map

| RTILB segment | Certification perimeter | Governed source | Technology | Governance metadata | Runtime locator |
| --- | --- | --- | --- | --- | --- |
| Credit | CREDIT | `Credito` | Power BI semantic model / OneLake catalog | Owner `TIPowerBI`; location `MS Área de Crédito` | `irrbb.sources.credit.power_bi` |
| Term deposits / certificates | LIABILITY | `Certificados` | Power BI semantic model / OneLake catalog | Owner `TIPowerBI`; location `MS Área de Ahorros` | `irrbb.sources.term_deposit.power_bi` |
| Borrowings / obligations with entities | LIABILITY | `Auxiliar Obligaciones Entidades 2026.xlsx` | Excel workbook | Institutional auxiliary workbook | `irrbb.sources.borrowing.workbook` |
| Investments | INVESTMENT | `Portafolio de Inversiones` | Institutional portfolio master | Existing investment source perimeter | `irrbb.sources.investment.portfolio_master` |

The Power BI catalog names, owner and organizational locations are source-governance identities.
They are not table names, DAX queries, XMLA endpoints, workspace IDs or proof of contractual field
availability.

## Current operational evidence for obligations

The currently reported workstation-visible path for the obligations workbook is:

```text
C:\Users\ahidalgo\OneDrive - COOPEALIANZA R.L\RESPALDO\AUXILIAR OBLIGACIONES\Auxiliar Obligaciones Entidades 2026.xlsx
```

This path is **operational evidence only**. It is intentionally absent from production source
registry code because it embeds a workstation/user-specific OneDrive location. Deployment must
resolve `irrbb.sources.borrowing.workbook` through external configuration appropriate to the
machine or service account executing AIP Enterprise.

## Fail-closed invariants

1. Each registered physical segment has exactly one source identity. Duplicate segments, source IDs
   or configuration keys are rejected.
2. A missing segment lookup raises an error. The registry never falls back to a different source.
3. The registry contains no `READY`, `INCOMPLETE` or `BLOCKED` state. Physical-source designation
   cannot bypass source certification.
4. No personal workstation path, credential, access token, semantic-model schema or endpoint is
   embedded in application-layer contracts.
5. `Credito` and `Certificados` remain schema-**NOT_ASSESSED** until their semantic-model entities,
   fields, grain, effective-date behavior and extraction evidence are inspected.
6. The obligations workbook remains schema-**NOT_ASSESSED** until its sheets, columns, row grain and
   contractual coverage are inspected.
7. The investment source continues through the already implemented investment reader, evidence
   assessor, certification gate and canonical mapper/bridge. Phase 16 does not weaken those gates.

## Explicit exclusions

### ICL

The Institutional ICL source is a regulatory liquidity aggregation. It is not registered as a
contractual liability-position source and must not be used to manufacture certificate or borrowing
contracts.

### SQL `VISTA_1514_1515_1516`

The existing SQL view is not registered as a contractual credit or liability fallback. Its presence
in configured sources is not evidence that it exposes operation-level principal, contractual rate,
maturity, repricing or cash-flow schedules. It may only be reconsidered if its actual schema and
grain are evidenced and separately certified.

## Architecture boundary

The dependency direction remains:

```text
Institutional source designation
        ↓
IRRBBPhysicalSourceRegistry
        ↓
Physical adapter / reader (future for Power BI and obligations workbook)
        ↓
Evidence assessor
        ↓
IRRBBSourceCertificationReport
        ↓
Certification gate
        ↓
Canonical position mapper
        ↓
IRRBBSourceSnapshotAssembler
        ↓
IRRBB domain
```

The registry resides in the application layer as source-technology metadata only. The configured
product layer owns the Coopealianza-specific source identities. No Power BI SDK, OneLake client,
Excel reader or filesystem lookup is introduced into the domain.

## Phase boundary

Phase 16 does **not**:

- connect to Power BI, Fabric or OneLake;
- infer semantic-model tables, columns, measures, relationships or row grain;
- read the obligations workbook;
- certify credit, certificates or borrowings as `READY`;
- add a fallback to ICL or the generic SQL view;
- alter investment mappings or IRRBB calculations;
- wire the new registry into production runtime composition.

A later phase may implement one physical adapter at a time. Each adapter must first preserve source
lineage and expose enough evidence to assess the corresponding versioned canonical requirement
profile. Production composition remains blocked until the applicable certification report is
`READY` and row-level mapping succeeds.
