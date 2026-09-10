# IRRBB / RTILB — Phase 9 Source Anti-Corruption Layer

## 1. Scope

Phase 9 prepares the ingestion boundary without selecting SQL Server, XML, Excel,
OneDrive, PostgreSQL, an API, or any other physical source.

The approved flow is:

```text
Physical source record
        |
        v
IRRBBSourceRecordEnvelope[T]
        |
        v
IRRBBCanonicalPositionMapper[T]
        |
        +--> IRRBBPositionSourceRecord
        |
        +--> IRRBBSourceMappingFailure
        |
        v
IRRBBSourceSnapshotAssembler
        |
        v
IRRBBSourceSnapshot
        |
        v
LoadIRRBBSourceSnapshot
        |
        v
IRRBBPositionDataQualityService
```

The mapper is adapter-owned. The domain never sees physical field names or storage
technology.

## 2. Non-negotiable behavior

- Missing source data is never converted to zero.
- A source record that cannot cross the canonical boundary is never silently dropped.
- Mapping failures retain `source_record_id`, `source_reference`, a stable failure code,
  the affected canonical field when known, and an explanatory message.
- Mapping failures make an otherwise empty load `BLOCKED`.
- If usable canonical positions coexist with mapping failures, the load remains
  `PARTIAL` rather than `READY`.
- The existing domain data-quality service remains the authority for canonical
  position readiness. Phase 9 does not duplicate its financial rules.
- Source lineage must survive mapping unchanged.

## 3. Canonical mapping failure codes

The ACL exposes source-independent failure categories only:

- `MISSING_REQUIRED_CANONICAL_FIELD`
- `INVALID_CANONICAL_VALUE`
- `UNSUPPORTED_SOURCE_VALUE`
- `SOURCE_RECORD_REJECTED`

A future SQL/XML/Excel adapter may diagnose its own physical field, but the canonical
contract records only the affected IRRBB concept. No physical schema is hardcoded here.

## 4. Source-sufficiency worksheet

This worksheet implements the required assessment format before a physical source is
selected. `NOT_ASSESSED` means that availability cannot be determined until an actual
schema, XSD, data dictionary, query result, workbook, or API contract is supplied.

| Variable RTILB | Crédito | Pasivos | Inversiones | Dato nativo esperado | Dato derivable | Faltante físico actual | Regla de derivación permitida | Fuente complementaria posible |
|---|---|---|---|---|---|---|---|---|
| `cutoff_date` | Requerido | Requerido | Requerido | Sí | No | NOT_ASSESSED | Ninguna | Ninguna |
| `position_id` | Requerido | Requerido | Requerido | Sí | Solo con identificador estable documentado | NOT_ASSESSED | Concatenación únicamente si garantiza unicidad y trazabilidad | Ninguna |
| `source_reference` | Requerido | Requerido | Requerido | Sí | No | NOT_ASSESSED | Ninguna | Metadata del adaptador |
| `product_type` | Requerido | Requerido | Requerido | Sí | Condicional | NOT_ASSESSED | Tabla de mapeo versionada y aprobada | Catálogo institucional |
| `instrument_class` | Requerido | Requerido | Requerido | Preferido | Sí | NOT_ASSESSED | Mapeo versionado desde producto/cuenta, nunca heurística silenciosa | Catálogo institucional / contable |
| `side` | Activo | Pasivo / fuera de balance | Activo | Preferido | Sí | NOT_ASSESSED | Derivación determinística desde clasificación aprobada | Catálogo contable |
| `currency` | Requerido | Requerido | Requerido | Sí | No | NOT_ASSESSED | Ninguna | Ninguna |
| `principal` / saldo vigente | Requerido | Requerido | Requerido | Sí | Condicional | NOT_ASSESSED | Solo desde componentes contractuales completos y reconciliables | Contabilidad / sistema transaccional |
| `carrying_amount` | Reconciliación | Reconciliación | Reconciliación | Preferido | Condicional | NOT_ASSESSED | Regla contable documentada | Contabilidad |
| `rate_type` | Requerido | Requerido cuando aplica | Requerido | Sí | Condicional | NOT_ASSESSED | Mapeo versionado desde términos contractuales | Catálogo de producto |
| `contractual_rate` | Requerido salvo schedule suficiente | Requerido salvo schedule suficiente | Requerido salvo cero cupón/schedule | Sí | No para sustituir ausencia | NOT_ASSESSED | No imputar | Sistema contractual |
| `reference_rate` | Variable | Variable | Variable | Preferido | No | NOT_ASSESSED | No inferir por producto sin regla aprobada | Catálogo contractual |
| `spread` | Variable | Variable | Variable | Preferido | Condicional | NOT_ASSESSED | Tasa contractual menos referencia solo si ambas corresponden al mismo fixing | Sistema contractual / tasas de referencia |
| `maturity_date` | Requerido | Requerido para plazo | Requerido | Sí | Condicional | NOT_ASSESSED | Solo desde calendario contractual completo | Sistema contractual |
| `next_repricing_date` | Variable | Variable | Variable | Preferido | Sí, si términos completos | NOT_ASSESSED | Fecha contractual de próximo reset; nunca usar vencimiento por defecto | Sistema contractual |
| `repricing_frequency_months` | Variable | Variable | Variable | Sí | Condicional | NOT_ASSESSED | Desde periodicidad contractual inequívoca | Catálogo contractual |
| `payment_frequency_months` | Requerido si no hay schedule | Requerido si no hay schedule | Requerido si cupón y no hay schedule | Sí | Condicional | NOT_ASSESSED | Desde periodicidad contractual inequívoca | Catálogo contractual |
| `payment_structure` | Requerido | Requerido cuando aplica | Requerido | Preferido | Sí | NOT_ASSESSED | Mapeo versionado desde contrato/producto | Catálogo institucional |
| contractual cash-flow schedule | Preferido / requerido para amortizantes | Requerido según estructura | Reutilizar motor contractual existente | Preferido | Sí con términos completos | NOT_ASSESSED | Generación contractual determinística; inversiones usan `PortfolioContractualCashFlowService` | Sistema contractual |
| `optionality` | Prepago cuando aplica | Retiro anticipado / NMD | Según instrumento | Sí | No | NOT_ASSESSED | No inferir comportamiento | Política/modelo aprobado |
| behavioral parameters | Condicional | Condicional / NMD | Condicional | No necesariamente contractual | No | NOT_ASSESSED | Solo metodología aprobada y versionada | Repositorio de supuestos aprobado |
| yield curve points | EVE | EVE | EVE | Mercado | Interpolación solo con metodología aprobada | NOT_ASSESSED | No inventar tenor/shock | Curvas soberanas / proveedor aprobado |
| FX reporting rate | Moneda extranjera | Moneda extranjera | Moneda extranjera | Mercado | No | NOT_ASSESSED | Regla regulatoria de fecha/conversión | BCCR |
| Capital Nivel 1 | Ratio RTILB | Ratio RTILB | Ratio RTILB | Sí | No | NOT_ASSESSED | Ninguna | Fuente regulatoria/financiera aprobada |

## 5. Gate before selecting a physical adapter

A physical candidate is not approved merely because it can create a
`BankingBookPosition`. Before production composition, its mapping matrix must classify
every required variable as one of:

- `NATIVE_AVAILABLE`
- `DERIVABLE_WITH_DOCUMENTED_RULE`
- `AVAILABLE_FROM_SUPPLEMENTARY_SOURCE`
- `MISSING_BLOCKING_GAP`
- `MISSING_BLOCKING_EVE`
- `NOT_APPLICABLE`

Every derivation rule must identify its source fields, effective date/version, and test
coverage. Fields that remain `NOT_ASSESSED` cannot be represented as available.

## 6. Next implementation gate

Phase 9 can be considered complete when:

1. the ACL contracts and assembler pass CI;
2. unmappable records remain visible in load status and diagnostics;
3. source lineage is preserved end-to-end;
4. the source-sufficiency worksheet remains physical-source neutral;
5. no SQL/XML/Excel/OneDrive/PostgreSQL/API schema has leaked into domain or application
   contracts.
