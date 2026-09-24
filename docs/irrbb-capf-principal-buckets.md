# CAPF principal temporal assignment

`CaptacionesCAPFPrincipalBucketBridge` accepts a CAPF fact already joined by
the certified certificate/operation key and an explicit cutoff. The caller is
responsible for supplying XML and contractual evidence from that same cutoff.
This slice does not establish source-cut consistency by inspecting files.

The bridge uses the existing account classifier to reject sight, matured-account
and unsupported families, then validates fixed-rate consistency, maturity
consistency, issue date and expired maturity. It calls `IRRBBTimeBucketService`
with the actual contractual maturity. Maturity at the cutoff follows the domain
service's existing overnight convention; earlier dates are explicit failures.

The output retains the joined XML/XLSX facts, the canonical assignment and the
versioned rule reference. Its amount is XML principal in its canonical currency;
XML accrued product and workbook colonized amounts are not added to it.
`eve_ready` is always false. No coupons, capitalized interest, aggregate GAP or
economic value are generated. This is a temporal principal component, not a
complete CAPF valuation or a production monthly ingestion activation.

Tests cover the join-to-bucket path, calendar month boundaries, over-20-year
maturity, source/principal preservation and rejection of unsupported accounts,
contracts not yet issued and past maturities. All fixtures are synthetic.
