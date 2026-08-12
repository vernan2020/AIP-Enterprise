from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class InstitutionalMatchResult:
    match_method: str
    confidence: float
    matched_vector_record: dict[str, Any] | None
    ambiguous: bool
    unmatched: bool


class InstitutionalPortfolioMatchingService:
    def enrich_positions(self, master_positions: list[dict[str, Any]], vector_records: list[dict[str, Any]], *, diagnostic_mode: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        normalized_vector_records = [self._normalize_vector_record(record) for record in vector_records]
        print(f"[instrumentation] InstitutionalMatchingService.enrich_positions vector_records_len={len(vector_records)}", flush=True)
        print(f"[instrumentation] STEP3 len(vector_positions)={len(normalized_vector_records)}", flush=True)
        self._emit_b180429_trace("STEP3", normalized_vector_records)
        if normalized_vector_records:
            first_record = normalized_vector_records[0]
            print(
                f"[instrumentation] first_accepted_record issuer={first_record.get('issuer', '')} product_code={first_record.get('instrument_type_or_mnemonic', '')} series={first_record.get('series_or_security_code', '')} maturity_date={self._serialize_date(first_record.get('maturity_date_if_present'))}",
                flush=True,
            )
        else:
            print("[instrumentation] first_accepted_record=None", flush=True)
        enriched_positions: list[dict[str, Any]] = []
        match_summary: dict[str, Any] = {
            "exact_isin_matches": 0,
            "series_maturity_matches": 0,
            "issuer_product_maturity_matches": 0,
            "ambiguous_matches": 0,
            "unmatched_positions": 0,
            "unused_vector_records": 0,
            "match_percentage": 0.0,
            "vector_keys_generated": 0,
            "vector_key_collisions": 0,
            "vector_key_sample": None,
            "master_key_sample": None,
            "lookup_result": None,
            "reconciliation": {},
        }
        used_vector_indexes: set[int] = set()
        match_trace: list[dict[str, Any]] = []

        key_index: dict[str, list[dict[str, Any]]] = {}
        for record in normalized_vector_records:
            series_key = self._compose_key(self._normalize_text(record.get("series_or_security_code", "")), self._coerce_date(record.get("maturity_date_if_present")))
            issuer_product_key = self._compose_key(self._normalize_text(record.get("issuer", "")), self._normalize_text(record.get("instrument_type_or_mnemonic", "")), self._coerce_date(record.get("maturity_date_if_present")))
            if series_key:
                match_summary["vector_keys_generated"] += 1
                key_index.setdefault(series_key, []).append(record)
            if issuer_product_key:
                match_summary["vector_keys_generated"] += 1
                key_index.setdefault(issuer_product_key, []).append(record)

        lookup_keys_for_b180429 = [key for key in key_index if "b180429" in key.lower() or "tptba" in key.lower() or "g|" in key.lower()]
        print(f"[instrumentation] generated_lookup_keys_for_B180429={lookup_keys_for_b180429}", flush=True)
        for position in master_positions:
            if self._normalize_text(position.get("series", "")) != "b180429":
                continue
            maturity_date = self._coerce_date(position.get("maturity_date"))
            normalized_series = self._normalize_text(position.get("series", ""))
            series_maturity_key = self._compose_key(normalized_series, maturity_date)
            issuer_product_maturity_key = self._compose_key(self._normalize_text(position.get("issuer", "")), self._normalize_text(position.get("product_code", "")), maturity_date)
            print(f"[instrumentation] STEP4 series_maturity={series_maturity_key}", flush=True)
            print(f"[instrumentation] STEP4 issuer_product_maturity={issuer_product_maturity_key}", flush=True)
            print(f"[instrumentation] STEP5 master_series_maturity_key={series_maturity_key}", flush=True)
            print(f"[instrumentation] STEP5 master_issuer_product_maturity_key={issuer_product_maturity_key}", flush=True)
            lookup_series = key_index.get(series_maturity_key)
            lookup_issuer_product = key_index.get(issuer_product_maturity_key)
            print(f"[instrumentation] STEP6 lookup(series_maturity)={lookup_series if lookup_series is not None else None}", flush=True)
            print(f"[instrumentation] STEP6 lookup(issuer_product_maturity)={lookup_issuer_product if lookup_issuer_product is not None else None}", flush=True)
            if lookup_series is None:
                print(f"[instrumentation] STEP6 reason=series_maturity key '{series_maturity_key}' missing from lookup index", flush=True)
            if lookup_issuer_product is None:
                print(f"[instrumentation] STEP6 reason=issuer_product_maturity key '{issuer_product_maturity_key}' missing from lookup index", flush=True)
            break

        reconciliation = self._build_reconciliation(master_positions, normalized_vector_records)
        match_summary["reconciliation"] = reconciliation

        for position in master_positions:
            match_result = self._match_position(position, normalized_vector_records)
            if self._normalize_text(position.get("series", "")) == "b180429" and match_result.unmatched:
                print("[instrumentation] STEP7 B180429 disappeared in _match_position", flush=True)
            elif self._normalize_text(position.get("series", "")) == "b180429":
                print(f"[instrumentation] STEP7 B180429 survived in _match_position via {match_result.match_method}", flush=True)
            enriched_position = dict(position)
            enriched_position["matching_diagnostics"] = self._build_position_diagnostics(position)
            enriched_position["vector_match"] = {
                "match_method": match_result.match_method,
                "confidence": match_result.confidence,
                "ambiguous": match_result.ambiguous,
                "matched": not match_result.unmatched,
            }
            if match_result.matched_vector_record is not None:
                enriched_position["vector_record"] = match_result.matched_vector_record
                if match_result.match_method == "EXACT_ISIN":
                    match_summary["exact_isin_matches"] += 1
                elif match_result.match_method == "SERIES_MATURITY":
                    match_summary["series_maturity_matches"] += 1
                elif match_result.match_method == "ISSUER_PRODUCT_MATURITY":
                    match_summary["issuer_product_maturity_matches"] += 1
                if match_result.matched_vector_record.get("source_index") is not None:
                    used_vector_indexes.add(int(match_result.matched_vector_record["source_index"]))
            else:
                match_summary["unmatched_positions"] += 1
                enriched_position["vector_match"]["match_method"] = "NO_VECTOR_MATCH"
            if match_result.ambiguous:
                match_summary["ambiguous_matches"] += 1
            if diagnostic_mode:
                match_trace.append({
                    "isin": position.get("isin"),
                    "normalized_isin": self._normalize_text(position.get("isin", "")),
                    "normalized_series": self._normalize_text(position.get("series", "")),
                    "normalized_issuer": self._normalize_text(position.get("issuer", "")),
                    "normalized_product_code": self._normalize_text(position.get("product_code", "")),
                    "maturity_date": self._serialize_date(position.get("maturity_date")),
                    "status": "matched" if match_result.matched_vector_record is not None else "unmatched",
                    "match_method": match_result.match_method,
                    "ambiguous": match_result.ambiguous,
                    "reason": "matched_vector_record" if match_result.matched_vector_record is not None else "no_vector_match",
                })
            enriched_positions.append(enriched_position)

        match_summary["unused_vector_records"] = len(normalized_vector_records) - len(used_vector_indexes)
        total_positions = len(enriched_positions)
        if total_positions:
            match_summary["match_percentage"] = round((total_positions - match_summary["unmatched_positions"]) / total_positions * 100.0, 2)
        if diagnostic_mode:
            match_summary["trace"] = match_trace

        if master_positions:
            sample_position = master_positions[0]
            series_key = self._compose_key(self._normalize_text(sample_position.get("series", "")), self._coerce_date(sample_position.get("maturity_date")))
            issuer_product_key = self._compose_key(self._normalize_text(sample_position.get("issuer", "")), self._normalize_text(sample_position.get("product_code", "")), self._coerce_date(sample_position.get("maturity_date")))
            match_summary["master_key_sample"] = {
                "series_maturity": series_key,
                "issuer_product_maturity": issuer_product_key,
            }
            if series_key:
                match_summary["lookup_result"] = {
                    "series_maturity": key_index.get(series_key, []),
                    "issuer_product_maturity": key_index.get(issuer_product_key, []),
                }

        if match_summary.get("vector_keys_generated", 0):
            match_summary["vector_key_collisions"] = sum(1 for items in key_index.values() if len(items) > 1)
            sample_key = next(iter(key_index), None)
            if sample_key is not None:
                match_summary["vector_key_sample"] = {
                    "series_maturity": sample_key,
                    "records": [record.get("raw", record) for record in key_index[sample_key][:3]],
                }
        for position in master_positions:
            normalized_series = self._normalize_text(position.get("series", ""))
            if normalized_series != "b180429":
                continue
            maturity_date = self._coerce_date(position.get("maturity_date"))
            series_maturity_key = self._compose_key(normalized_series, maturity_date)
            lookup = key_index.get(series_maturity_key)
            print(f"[instrumentation] lookup.get({series_maturity_key}) -> {lookup if lookup is not None else None}", flush=True)
            if lookup is None:
                first_record = normalized_vector_records[0] if normalized_vector_records else None
                print(
                    f"[instrumentation] key_disappeared_reason: series_maturity_key='{series_maturity_key}' was not present in key_index. normalized_vector_records={len(normalized_vector_records)}; first_record_series={first_record.get('series_or_security_code', '') if first_record else None}; first_record_maturity={self._serialize_date(first_record.get('maturity_date_if_present')) if first_record else None}; built_series_key_from_first_record={self._compose_key(self._normalize_text(first_record.get('series_or_security_code', '')), self._coerce_date(first_record.get('maturity_date_if_present'))) if first_record else None}; available_lookup_keys={sorted(key_index.keys())[:10]}",
                    flush=True,
                )

        return enriched_positions, match_summary

    def _build_reconciliation(self, master_positions: list[dict[str, Any]], vector_records: list[dict[str, Any]]) -> dict[str, Any]:
        eligible_positions = []
        position_reconciliation: list[dict[str, Any]] = []
        unmatched_reason_groups: dict[str, int] = {
            "no maturity / perpetual / fund": 0,
            "equity or participation instrument": 0,
            "closed position": 0,
            "instrument not expected in PiPCA": 0,
            "series absent from vector": 0,
            "maturity mismatch": 0,
            "parsing/normalization issue": 0,
            "other": 0,
        }
        collision_details: list[dict[str, Any]] = []
        key_index: dict[str, list[dict[str, Any]]] = {}
        for record in vector_records:
            series_key = self._compose_key(self._normalize_text(record.get("series_or_security_code", "")), self._coerce_date(record.get("maturity_date_if_present")))
            if series_key:
                key_index.setdefault(series_key, []).append(record)
        for series_key, records in sorted(key_index.items()):
            if len(records) <= 1:
                continue
            collision_details.append({
                "key": series_key,
                "number_of_records": len(records),
                "true_duplicates": self._is_duplicate_group(records),
                "price_or_yield_differs": self._has_conflicting_values(records),
                "uses_matched_master_position": self._collision_affects_master_position(master_positions, series_key),
            })
        for position in master_positions:
            series = self._normalize_text(position.get("series", ""))
            maturity = self._coerce_date(position.get("maturity_date"))
            issuer = self._normalize_text(position.get("issuer", ""))
            product_code = self._normalize_text(position.get("product_code", ""))
            is_eligible_fixed_income = self._is_eligible_fixed_income(position)
            if is_eligible_fixed_income:
                eligible_positions.append(position)
            classification = "MATCHED"
            reason = ""
            if self._normalize_text(position.get("isin", "")):
                matched = any(self._normalize_text(record.get("isin_if_present", "")) == self._normalize_text(position.get("isin", "")) for record in vector_records)
                if not matched:
                    classification = "UNMATCHED_REQUIRES_REVIEW"
                    reason = "parsing/normalization issue"
            elif self._is_no_maturity_or_fund(position):
                classification = "UNMATCHED_EXPECTED"
                reason = "no maturity / perpetual / fund"
            elif self._is_equity_or_participation(position):
                classification = "UNMATCHED_EXPECTED"
                reason = "equity or participation instrument"
            elif self._is_closed_position(position):
                classification = "UNMATCHED_EXPECTED"
                reason = "closed position"
            elif self._is_instrument_not_expected_in_pipca(position):
                classification = "UNMATCHED_EXPECTED"
                reason = "instrument not expected in PiPCA"
            elif not series:
                classification = "UNMATCHED_REQUIRES_REVIEW"
                reason = "parsing/normalization issue"
            elif not maturity:
                classification = "UNMATCHED_EXPECTED"
                reason = "no maturity / perpetual / fund"
            else:
                matching_key = self._compose_key(series, maturity)
                matching_records = [record for record in vector_records if self._normalize_text(record.get("series_or_security_code", "")) == series and self._coerce_date(record.get("maturity_date_if_present")) == maturity]
                if not matching_records:
                    classification = "UNMATCHED_REQUIRES_REVIEW"
                    reason = "series absent from vector"
                else:
                    deduped_records = self._deduplicate_records(matching_records)
                    if len(deduped_records) > 1:
                        if self._is_duplicate_group(deduped_records) and self._has_conflicting_values(deduped_records) is False:
                            classification = "MATCHED"
                        else:
                            classification = "UNMATCHED_REQUIRES_REVIEW"
                            reason = "parsing/normalization issue"
                    else:
                        classification = "MATCHED"
            if classification == "MATCHED" and not is_eligible_fixed_income:
                classification = "UNMATCHED_EXPECTED"
                reason = "instrument not expected in PiPCA"
            if classification != "MATCHED" and reason:
                unmatched_reason_groups[self._reason_group(reason)] += 1
            position_reconciliation.append({
                "issuer": issuer,
                "product_code": product_code,
                "classification": classification,
                "series": series,
                "isin": self._normalize_text(position.get("isin", "")),
                "maturity_date": self._serialize_date(maturity),
                "market_value": position.get("market_value"),
                "reason_no_match": reason,
            })
        matched_positions = sum(1 for item in position_reconciliation if item["classification"] == "MATCHED")
        expected_unmatched = sum(1 for item in position_reconciliation if item["classification"] == "UNMATCHED_EXPECTED")
        review_required = sum(1 for item in position_reconciliation if item["classification"] == "UNMATCHED_REQUIRES_REVIEW")
        raw_match_percentage = round((matched_positions / len(master_positions) * 100.0) if master_positions else 0.0, 1)
        eligible_match_percentage = round((matched_positions / len(eligible_positions) * 100.0) if eligible_positions else 0.0, 1)
        return {
            "total_master_positions": len(master_positions),
            "eligible_fixed_income_positions": len(eligible_positions),
            "matched_positions": matched_positions,
            "expected_unmatched_positions": expected_unmatched,
            "review_required_positions": review_required,
            "raw_match_percentage": raw_match_percentage,
            "eligible_match_percentage": eligible_match_percentage,
            "position_reconciliation": position_reconciliation,
            "unmatched_reason_groups": unmatched_reason_groups,
            "vector_key_collisions": len(collision_details),
            "collisions_affecting_portfolio": sum(1 for item in collision_details if item["uses_matched_master_position"]),
            "collision_details": collision_details,
            "deduplication_strategy": "When duplicate PiPCA records share the same normalized series/maturity key and identical issuer/product/market price/yield values, keep the earliest record by source index for diagnostics and do not use conflicting duplicates for VER matching.",
            "known_government_positions": {
                "B180429": self._build_known_position_entry(position_reconciliation, "b180429"),
                "S240327": self._build_known_position_entry(position_reconciliation, "s240327"),
                "CRS240129": self._build_known_position_entry(position_reconciliation, "crs240129"),
            },
        }

    def _build_known_position_entry(self, position_reconciliation: list[dict[str, Any]], series: str) -> dict[str, Any]:
        for item in position_reconciliation:
            if self._normalize_text(item.get("series")) == self._normalize_text(series):
                return {
                    "classification": item["classification"],
                    "issuer": item["issuer"],
                    "product_code": item["product_code"],
                    "maturity_date": item["maturity_date"],
                    "reason_no_match": item["reason_no_match"],
                }
        return {}

    def _is_duplicate_group(self, records: list[dict[str, Any]]) -> bool:
        if not records:
            return False
        reference = records[0]
        for record in records[1:]:
            if self._normalize_text(record.get("series_or_security_code", "")) != self._normalize_text(reference.get("series_or_security_code", "")):
                return False
            if self._normalize_text(record.get("issuer", "")) != self._normalize_text(reference.get("issuer", "")):
                return False
            if self._normalize_text(record.get("instrument_type_or_mnemonic", "")) != self._normalize_text(reference.get("instrument_type_or_mnemonic", "")):
                return False
            if self._coerce_date(record.get("maturity_date_if_present")) != self._coerce_date(reference.get("maturity_date_if_present")):
                return False
        return True

    def _has_conflicting_values(self, records: list[dict[str, Any]]) -> bool:
        if len(records) < 2:
            return False
        reference_price = records[0].get("market_price")
        reference_yield = records[0].get("market_yield")
        for record in records[1:]:
            if record.get("market_price") != reference_price or record.get("market_yield") != reference_yield:
                return True
        return False

    def _deduplicate_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        indexed_records = list(enumerate(records))
        indexed_records.sort(
            key=lambda item: (
                item[1].get("source_index") is None,
                int(item[1].get("source_index", 0)) if item[1].get("source_index") is not None else 0,
                item[0],
            )
        )
        for _, record in indexed_records:
            identity = (
                self._normalize_text(record.get("issuer", "")),
                self._normalize_text(record.get("instrument_type_or_mnemonic", "")),
                self._normalize_text(record.get("series_or_security_code", "")),
                self._serialize_date(self._coerce_date(record.get("maturity_date_if_present"))),
            )
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(record)
        return deduped

    def _collision_affects_master_position(self, master_positions: list[dict[str, Any]], collision_key: str) -> bool:
        for position in master_positions:
            series = self._normalize_text(position.get("series", ""))
            maturity = self._coerce_date(position.get("maturity_date"))
            if self._compose_key(series, maturity) == collision_key:
                return True
        return False

    def _reason_group(self, reason: str) -> str:
        mapping = {
            "no maturity / perpetual / fund": "no maturity / perpetual / fund",
            "equity or participation instrument": "equity or participation instrument",
            "closed position": "closed position",
            "instrument not expected in PiPCA": "instrument not expected in PiPCA",
            "series absent from vector": "series absent from vector",
            "maturity mismatch": "maturity mismatch",
            "parsing/normalization issue": "parsing/normalization issue",
        }
        return mapping.get(reason, "other")

    def _is_no_maturity_or_fund(self, position: dict[str, Any]) -> bool:
        product_code = self._normalize_text(position.get("product_code", ""))
        series = self._normalize_text(position.get("series", ""))
        return not self._coerce_date(position.get("maturity_date")) or product_code in {"fund", "fondo"} or series.startswith("fund")

    def _is_equity_or_participation(self, position: dict[str, Any]) -> bool:
        product_code = self._normalize_text(position.get("product_code", ""))
        issuer = self._normalize_text(position.get("issuer", ""))
        return "equity" in product_code or "particip" in product_code or "accion" in issuer.lower() or "particip" in issuer.lower()

    def _is_closed_position(self, position: dict[str, Any]) -> bool:
        return self._normalize_text(position.get("classification", "")) in {"cerrado", "closed", "closed_position"}

    def _is_instrument_not_expected_in_pipca(self, position: dict[str, Any]) -> bool:
        product_code = self._normalize_text(position.get("product_code", ""))
        return product_code in {"fund", "fondo", "equity", "acciones", "participation"}

    def _is_eligible_fixed_income(self, position: dict[str, Any]) -> bool:
        if self._is_no_maturity_or_fund(position):
            return False
        if self._is_equity_or_participation(position):
            return False
        if self._is_closed_position(position):
            return False
        if self._is_instrument_not_expected_in_pipca(position):
            return False
        return True

    def _emit_b180429_trace(self, step: str, records: list[dict[str, Any]]) -> None:
        for record in records:
            if self._normalize_text(record.get("series_or_security_code", "")) != "b180429":
                continue
            print(
                f"[instrumentation] {step} issuer={record.get('issuer', '')} product_code={record.get('instrument_type_or_mnemonic', '')} series={record.get('series_or_security_code', '')} maturity_date={self._serialize_date(record.get('maturity_date_if_present'))}",
                flush=True,
            )

    def _normalize_vector_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "issuer": self._normalize_text(record.get("issuer", "")),
            "instrument_type_or_mnemonic": self._normalize_text(record.get("instrument_type_or_mnemonic", "")),
            "series_or_security_code": self._normalize_text(record.get("series_or_security_code", "")),
            "normalized_issuer_key": self._normalize_text(record.get("issuer", "")),
            "normalized_series_key": self._normalize_text(record.get("series_or_security_code", "")),
            "isin_if_present": self._normalize_text(record.get("isin_if_present", "")),
            "maturity_date_if_present": record.get("maturity_date_if_present"),
            "source_index": record.get("source_index"),
            "source_line": record.get("source_line"),
            "raw": record,
        }

    def _match_position(self, position: dict[str, Any], vector_records: list[dict[str, Any]]) -> InstitutionalMatchResult:
        isin = self._normalize_text(position.get("isin", ""))
        series = self._normalize_text(position.get("series", ""))
        maturity_date = self._coerce_date(position.get("maturity_date"))
        issuer = self._normalize_text(position.get("issuer", ""))
        product_code = self._normalize_text(position.get("product_code", ""))
        print(
            f"[instrumentation] matching_position series={series} maturity={maturity_date.isoformat() if maturity_date else None} issuer={issuer} product_code={product_code} isin={isin}",
            flush=True,
        )
        if isin:
            candidates = [record for record in vector_records if self._normalize_text(record.get("isin_if_present", "")) == isin]
            print(f"[instrumentation] exact_isin_candidates={len(candidates)}", flush=True)
            if len(candidates) == 1:
                return InstitutionalMatchResult("EXACT_ISIN", 1.0, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("EXACT_ISIN", 0.9, None, True, True)

        if series and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("series_or_security_code", "")) == series and record.get("maturity_date_if_present") == maturity_date]
            print(f"[instrumentation] series_maturity_candidates={len(candidates)}", flush=True)
            if len(candidates) == 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.8, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.7, None, True, True)

        if issuer and product_code and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("issuer", "")) == issuer and self._normalize_text(record.get("instrument_type_or_mnemonic", "")) == product_code and record.get("maturity_date_if_present") == maturity_date]
            print(f"[instrumentation] issuer_product_maturity_candidates={len(candidates)}", flush=True)
            if len(candidates) == 1:
                return InstitutionalMatchResult("ISSUER_PRODUCT_MATURITY", 0.6, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("ISSUER_PRODUCT_MATURITY", 0.5, None, True, True)

        return InstitutionalMatchResult("NO_VECTOR_MATCH", 0.0, None, False, True)

    def _build_position_diagnostics(self, position: dict[str, Any]) -> dict[str, Any]:
        maturity_date = self._coerce_date(position.get("maturity_date"))
        normalized_isin = self._normalize_text(position.get("isin", ""))
        normalized_series = self._normalize_text(position.get("series", ""))
        normalized_issuer = self._normalize_text(position.get("issuer", ""))
        normalized_product_code = self._normalize_text(position.get("product_code", ""))
        return {
            "normalized_isin": normalized_isin,
            "normalized_series": normalized_series,
            "normalized_issuer": normalized_issuer,
            "normalized_product_code": normalized_product_code,
            "maturity_date": maturity_date.isoformat() if maturity_date else None,
            "matching_keys": {
                "exact_isin": normalized_isin,
                "series_maturity": self._compose_key(normalized_series, maturity_date),
                "issuer_product_maturity": self._compose_key(normalized_issuer, normalized_product_code, maturity_date),
            },
        }

    def _compose_key(self, *parts: Any) -> str:
        values: list[str] = []
        for part in parts:
            if part in (None, ""):
                continue
            if isinstance(part, date):
                values.append(part.isoformat())
            else:
                values.append(self._normalize_text(part))
        return "|".join(value for value in values if value)

    def _coerce_date(self, value: Any) -> date | None:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _serialize_date(self, value: Any) -> str | None:
        if isinstance(value, date):
            return value.isoformat()
        return None

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        return re.sub(r"\s+", "", text).casefold()
