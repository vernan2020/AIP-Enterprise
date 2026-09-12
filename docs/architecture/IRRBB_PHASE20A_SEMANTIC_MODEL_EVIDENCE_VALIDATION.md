# IRRBB Phase 20A — Semantic-model evidence validation

## Status

Phase 20A adds the transfer boundary for metadata-only inspection evidence from the governed Power BI semantic models `Credito` and `Certificados`. It does not connect to Power BI and does not map any field to RTILB contractual meaning.

## Purpose

Phase 20 established source-neutral application contracts and the `IRRBBSemanticModelMetadataInspector` port. This slice adds a strict JSON report contract plus a configured validator so evidence acquired later by an approved infrastructure adapter can be transferred, reviewed and validated before any source-requirement assessment begins.

## Fail-closed validation

The validator requires:

- exact report type and version;
- an exact `source_id` registered as either the governed `Credito` or `Certificados` semantic model;
- exact agreement between governed logical name and reported semantic-model name;
- non-blank runtime workspace and semantic-model references without hard-coding their values;
- a timezone-aware observation timestamp;
- an explicit supported schema-freshness state;
- `row_data_included=false`;
- `expressions_included=false`;
- at least one table and one physical column per table;
- exact nested JSON shapes with no unknown fields;
- physical column data types;
- measure identities only;
- relationships whose endpoints resolve to observed tables and columns.

The validator deliberately rejects added fields rather than silently accepting payload expansion. This prevents a future provider adapter from widening a metadata-only report into row-level or expression-bearing evidence without a reviewed contract change.

## Explicit non-goals

Phase 20A does not add REST, XMLA, DAX, authentication, tenant configuration, workspace/model IDs, service-principal configuration, runtime composition, source-requirement profiles, certification, RTILB aliases, canonical mapping, or UI behavior.

The next physical-access transition remains gated on institutional confirmation of the authorized Power BI metadata-scanning mechanism and the target workspace/model identities. Phase 19 for the obligations workbook remains separately blocked on the real Phase 18 JSON evidence.
