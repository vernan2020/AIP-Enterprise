# IRRBB Phase 20C — Governed semantic-model inspection orchestration

## Status

Phase 20C adds the configured orchestration boundary between the governed physical-source registry, the source-neutral semantic-model inspection port, and the validated evidence renderer introduced in Phases 20 through 20B.

This slice does not connect to Power BI or Fabric and does not assign RTILB contractual meaning to any discovered field.

## Purpose

A provider adapter will eventually implement `IRRBBSemanticModelMetadataInspector`. Without an orchestration boundary, a misconfigured adapter could be asked to inspect `Credito` yet return a valid snapshot for `Certificados`; both snapshots are individually governed, so the Phase 20B renderer alone cannot determine which source the caller actually requested.

`GovernedSemanticModelInspectionCoordinator` closes that gap. It resolves the institutional source by segment, invokes the injected inspector with that exact descriptor, verifies that the returned snapshot is bound to the same `source_id` and logical name, and only then renders the transferable evidence document.

## Fail-closed orchestration

The coordinator:

- resolves the source from `IRRBBPhysicalSourceRegistry` rather than accepting a free-form provider identifier;
- permits only sources whose physical kind is `POWER_BI_SEMANTIC_MODEL`;
- passes the exact governed descriptor to the injected inspector;
- rejects returned evidence whose `source_id` differs from the requested source;
- rejects returned evidence whose logical name differs from the requested source;
- delegates final evidence-shape and metadata-only validation to `SemanticModelInspectionEvidenceRenderer` and the Phase 20A validator;
- returns the governed descriptor, validated snapshot and deterministic evidence document as one immutable result.

The coordinator does not resolve tenant, workspace, semantic-model or authentication configuration. Those remain responsibilities of a future institutionally approved infrastructure adapter outside this boundary.

## Explicit exclusions

Phase 20C does not add:

- REST, XMLA, DAX or Admin Scanner connectivity;
- Microsoft Entra authentication or service-principal handling;
- tenant, workspace or semantic-model identifiers in source code;
- scanner-response parsing;
- production runtime composition;
- source requirement profiles or certification;
- RTILB aliases or contractual mapping;
- contractual rows, balances or cash-flow generation;
- UI behavior;
- changes to EVE, GAP, NII, DV01, VaR, HQLA or MIL calculations.

## Next gate

After Phase 20C the source-neutral Power BI inspection path is complete enough for provider implementation. The next provider-specific slice remains blocked until the institution confirms the authorized metadata-scanning mechanism and runtime identities for the governed `Credito` and `Certificados` models.

Any future adapter must resolve `source.configuration_key` outside application code, return metadata only, preserve `row_data_included=false` and `expressions_included=false`, and pass through this coordinator before evidence is accepted for source-requirement assessment.
