# IRRBB Phase 20 — Semantic-model inspection contracts

## Status

This slice defines the application boundary for safe semantic-model discovery for the governed `Credito` and `Certificados` Power BI sources. It intentionally does **not** implement authentication, HTTP/XMLA connectivity, runtime composition, RTILB aliases, contractual row extraction, or financial mapping.

## Decision

The application layer owns a source-neutral metadata-only inspection contract and a protocol port. A future infrastructure adapter must resolve each governed source `configuration_key` through deployment configuration and return an auditable `IRRBBSemanticModelInspectionSnapshot`.

The snapshot records runtime-observed provider workspace/model references, model name, inspection method, timezone-aware observation timestamp, schema freshness, tables, columns, physical data types, measures by identity only, and relationships when the approved provider mechanism exposes them. Provider IDs are evidence values supplied at runtime; they are not constants and must not be committed as institutional configuration.

The boundary is fail-closed:

- row data is forbidden;
- DAX/Mashup/model expressions are forbidden;
- empty schemas are rejected;
- duplicate table/column/measure names are rejected case-insensitively;
- relationship endpoints must resolve to observed tables and columns;
- no field receives RTILB business meaning in this phase.

## Microsoft mechanism assessment

Microsoft's Power BI/Fabric Admin Scanner APIs are the preferred candidate for the first physical implementation because they are explicitly designed for metadata scanning. `PostWorkspaceInfo` can request `datasetSchema=true`, and `GetScanResult` returns semantic-model metadata including table and column schema; Microsoft's documented sample also exposes a `relationships` collection. Metadata scanning is available across tenant metadata, including non-Premium workspaces, but it requires Fabric-administrator setup or an authorized service principal/delegated admin flow and the detailed metadata tenant setting.

Official references:

- https://learn.microsoft.com/en-us/fabric/governance/metadata-scanning-overview
- https://learn.microsoft.com/en-us/fabric/admin/metadata-scanning-setup
- https://learn.microsoft.com/en-us/rest/api/power-bi/admin/workspace-info-post-workspace-info
- https://learn.microsoft.com/en-us/rest/api/power-bi/admin/workspace-info-get-scan-result

`Execute Queries` / `Execute DAX Queries` are not selected for discovery because their purpose is query execution and result retrieval, which can cross the metadata-only boundary into model data.

XMLA remains a possible later adapter only if institutional evidence confirms that the target workspaces support XMLA and that the required access is authorized. Microsoft documents XMLA connectivity for Premium, Premium Per User, and Embedded workspaces, with DMV/TOM access to richer model metadata. No XMLA client dependency is introduced by this slice.

Official references:

- https://learn.microsoft.com/en-us/fabric/enterprise/powerbi/service-premium-connect-tools
- https://learn.microsoft.com/en-us/analysis-services/instances/use-dynamic-management-views-dmvs-to-monitor-analysis-services

## Required evidence before physical access

Before implementing the Power BI adapter, deployment must establish the authorized institutional mechanism and provide runtime configuration for the target workspace/model identities. Tokens, credentials, tenant identifiers, workspace identifiers, model identifiers, and endpoints remain outside source code.

Until that evidence exists, Phase 20 stops at the application port. Phase 19 for the borrowing workbook remains independently blocked on its real inspection JSON and is not bypassed by this work.
