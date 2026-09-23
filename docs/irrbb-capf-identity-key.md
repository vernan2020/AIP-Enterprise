# CAPF contractual identity key correction

The CAPF join uses exact source-text equality:

`Detalle Ahorro Plazo Fijo: Número Certificado = Pasivos_Cuentas_Contables_210.xml: IdOperacion`.

Evidence reviewed for this correction:

- `Informe_Reconstruccion_Brechas_Tasas_Agosto_2026.docx`, section 4.3,
  explicitly records this join for the August 2026 contractual workbook.
- `Especificacion_Tecnico_Funcional_Motor_Brechas_SICVECA_205_Actualizada.docx`,
  version 2.0 dated 2026-09-22, section 8.1, defines NumeroCertificado as
  `Llave = IdOperacion`.

This supersedes the missing-key-evidence statement in PR #303 and issue #66.
No per-certificate correspondence catalog is required. The service accepts
canonical text from the source normalization boundary; it does not cast keys to
numbers, remove leading zeros, case-fold identifiers, or guess another key.
Blank or noncanonical keys, duplicate certificates, absent matches and substituted
index records are rejected. A successful join retains both original facts and
the versioned rule reference. Callers must supply the same governed monthly cut.

Principal and canonical currency remain sourced from XML 210. Contractual maturity
and fixed-rate consistency checks remain in place. Product 346 capitalization
semantics are unchanged. The documents are used here only as identity-key evidence:
their SICVECA R1-R6 assignments, benchmark totals and other historical calculation
rules are not imported into IRRBB. This correction does not read Contable_Brecha.xml,
generate cash flows, activate GAP/EVE, or bypass protection on an XLSX file.

Validation uses synthetic unit fixtures, not a certification of a new monthly cut.
