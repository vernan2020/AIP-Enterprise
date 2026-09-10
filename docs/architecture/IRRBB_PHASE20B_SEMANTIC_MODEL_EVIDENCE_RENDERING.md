# IRRBB Phase 20B — Semantic-model evidence rendering

## Status

Phase 20B completes the source-neutral evidence-transfer boundary for the governed Power BI semantic models `Credito` and `Certificados`. It adds deterministic serialization from an already validated application snapshot into the versioned Phase 20A JSON contract.

This slice does not connect to Power BI or Fabric and does not interpret any semantic-model field as contractual RTILB data.

## Purpose

Phase 20 defined the metadata-only application contracts and inspection port. Phase 20A defined the strict transfer contract and validator. A future approved infrastructure adapter will eventually return an `IRRBBSemanticModelInspectionSnapshot`; Phase 20B ensures that snapshot is serialized through one reviewed path rather than allowing each provider adapter or diagnostic shell to invent its own evidence JSON.

## Fail-closed rendering

`SemanticModelInspectionEvidenceRenderer`:

- accepts only an `IRRBBSemanticModelInspectionSnapshot`;
- emits exactly the Phase 20A report shape;
- serializes source/model identity, observation metadata, schema, measure identities and relationships;
- does not expose row containers, DAX expressions, Mashup expressions, table source expressions or arbitrary provider payload fields;
- revalidates its own rendered payload through `SemanticModelInspectionEvidenceValidator` before returning it;
- emits deterministic JSON with stable key ordering for review and transfer.

The renderer does not make an inspection snapshot trustworthy merely by serializing it. Provider acquisition, authentication and source identity remain separate responsibilities of a future authorized infrastructure adapter.

## Explicit exclusions

Phase 20B does not add:

- HTTP, REST, XMLA or DAX connectivity;
- Power BI/Fabric authentication;
- tenant, workspace or semantic-model identifiers in source code;
- scanner-response parsing;
- runtime composition;
- source-requirement profiles or certification;
- RTILB aliases or canonical mapping;
- contractual rows or balances;
- UI behavior;
- changes to EVE, GAP, NII, DV01, VaR, HQLA or MIL calculations.

## Next gate

After Phase 20B, no further Power BI provider-specific implementation should proceed until institutional evidence confirms the authorized metadata-scanning mechanism and supplies the runtime identities needed to locate `Credito` and `Certificados` without hard-coding them.

The future provider adapter must remain metadata-only. If Power BI/Fabric Admin Scanner APIs are authorized, the intended request shape is `datasetSchema=true` and `datasetExpressions=false`; any raw response must be reduced to the Phase 20 application contract before it can be rendered as transferable evidence.
