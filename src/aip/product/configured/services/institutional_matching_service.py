from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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
        }
        used_vector_indexes: set[int] = set()
        match_trace: list[dict[str, Any]] = []

        key_index: dict[str, list[dict[str, Any]]] = {}
        trace_security = None
        trace_security_value = None
        if isinstance(vector_records, list):
            trace_security_value = None
        for record in normalized_vector_records:
            series_key = self._compose_key(self._normalize_text(record.get("series_or_security_code", "")), self._coerce_date(record.get("maturity_date_if_present")))
            issuer_product_key = self._compose_key(self._normalize_text(record.get("issuer", "")), self._normalize_text(record.get("instrument_type_or_mnemonic", "")), self._coerce_date(record.get("maturity_date_if_present")))
            if series_key:
                match_summary["vector_keys_generated"] += 1
                key_index.setdefault(series_key, []).append(record)
            if issuer_product_key:
                match_summary["vector_keys_generated"] += 1
                key_index.setdefault(issuer_product_key, []).append(record)

        for position in master_positions:
            match_result = self._match_position(position, normalized_vector_records)
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
        return enriched_positions, match_summary

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
        if isin:
            candidates = [record for record in vector_records if self._normalize_text(record.get("isin_if_present", "")) == isin]
            if len(candidates) == 1:
                return InstitutionalMatchResult("EXACT_ISIN", 1.0, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("EXACT_ISIN", 0.9, None, True, True)

        if series and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("series_or_security_code", "")) == series and record.get("maturity_date_if_present") == maturity_date]
            if len(candidates) == 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.8, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.7, None, True, True)

        if issuer and product_code and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("issuer", "")) == issuer and self._normalize_text(record.get("instrument_type_or_mnemonic", "")) == product_code and record.get("maturity_date_if_present") == maturity_date]
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
