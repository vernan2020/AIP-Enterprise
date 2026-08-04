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
        }
        used_vector_indexes: set[int] = set()
        match_trace: list[dict[str, Any]] = []

        for position in master_positions:
            match_result = self._match_position(position, normalized_vector_records)
            enriched_position = dict(position)
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
        return enriched_positions, match_summary

    def _normalize_vector_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "issuer": self._normalize_text(record.get("issuer", "")),
            "instrument_type_or_mnemonic": self._normalize_text(record.get("instrument_type_or_mnemonic", "")),
            "series_or_security_code": self._normalize_text(record.get("series_or_security_code", "")),
            "isin_if_present": self._normalize_text(record.get("isin_if_present", "")),
            "maturity_date_if_present": record.get("maturity_date_if_present"),
            "source_index": record.get("source_index"),
            "raw": record,
        }

    def _match_position(self, position: dict[str, Any], vector_records: list[dict[str, Any]]) -> InstitutionalMatchResult:
        isin = self._normalize_text(position.get("isin", ""))
        series = self._normalize_text(position.get("series", ""))
        maturity_date = position.get("maturity_date")
        issuer = self._normalize_text(position.get("issuer", ""))
        product_code = self._normalize_text(position.get("product_code", ""))
        if isin:
            candidates = [record for record in vector_records if self._normalize_text(record.get("isin_if_present", "")) == isin]
            if len(candidates) == 1:
                return InstitutionalMatchResult("EXACT_ISIN", 1.0, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("EXACT_ISIN", 0.9, None, True, False)

        if series and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("series_or_security_code", "")) == series and record.get("maturity_date_if_present") == maturity_date]
            if len(candidates) == 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.8, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("SERIES_MATURITY", 0.7, None, True, False)

        if issuer and product_code and maturity_date:
            candidates = [record for record in vector_records if self._normalize_text(record.get("issuer", "")) == issuer and self._normalize_text(record.get("instrument_type_or_mnemonic", "")) == product_code and record.get("maturity_date_if_present") == maturity_date]
            if len(candidates) == 1:
                return InstitutionalMatchResult("ISSUER_PRODUCT_MATURITY", 0.6, candidates[0], False, False)
            if len(candidates) > 1:
                return InstitutionalMatchResult("ISSUER_PRODUCT_MATURITY", 0.5, None, True, False)

        return InstitutionalMatchResult("NO_VECTOR_MATCH", 0.0, None, False, True)

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        return re.sub(r"\s+", "", text).casefold()
