from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol

from aip.application.irrbb import IRRBBSourceExclusion, IRRBBSourceMappingFailure
from aip.product.configured.irrbb.credit_xml_rate_risk_normalizer import (
    CreditXMLRateRiskFact,
    CreditXMLRateRiskNormalizer,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)


class CreditXMLMonthlySourcePort(Protocol):
    """Physical-source port required by the credit normalization batch bridge."""

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource: ...

    def iter_records(self, source: XMLConfiaResolvedSource) -> Iterable[XMLConfiaRecord]: ...

    def sha256(self, path: Path, *, chunk_size: int = 1024 * 1024) -> str: ...


@dataclass(frozen=True, slots=True)
class CreditXMLNormalizationBatchResult:
    """Auditable normalization result for one governed monthly credit XML."""

    cutoff_date: date
    source_file_name: str
    source_sha256: str
    source_record_count: int
    normalized_facts: tuple[CreditXMLRateRiskFact, ...]
    source_exclusions: tuple[IRRBBSourceExclusion, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        if not self.source_file_name.strip():
            raise ValueError("credit XML source_file_name is required")
        if len(self.source_sha256) != 64:
            raise ValueError("credit XML source_sha256 must be a SHA-256 hex digest")
        try:
            int(self.source_sha256, 16)
        except ValueError as exc:
            raise ValueError("credit XML source_sha256 must be hexadecimal") from exc
        if self.source_record_count < 0:
            raise ValueError("credit XML source_record_count cannot be negative")

        represented = (
            len(self.normalized_facts)
            + len(self.source_exclusions)
            + len(self.mapping_failures)
        )
        if represented != self.source_record_count:
            raise ValueError("every credit XML source record must have one normalization outcome")

        ids = (
            tuple(item.source_record_id for item in self.normalized_facts)
            + tuple(item.source_record_id for item in self.source_exclusions)
            + tuple(item.source_record_id for item in self.mapping_failures)
        )
        if len(ids) != len(set(ids)):
            raise ValueError("credit XML normalization outcomes must have unique source_record_id")


class CreditXMLMonthlyNormalizationBridge:
    """Resolve and normalize one monthly credit XML without activating IRRBB calculations."""

    SOURCE_KEY = "CREDIT"
    SOURCE_KIND = "XML_CONFIA"

    def __init__(
        self,
        *,
        source_reader: CreditXMLMonthlySourcePort,
        normalizer: CreditXMLRateRiskNormalizer | None = None,
    ) -> None:
        self._source_reader = source_reader
        self._normalizer = normalizer or CreditXMLRateRiskNormalizer()

    def normalize(self, *, cutoff_date: date) -> CreditXMLNormalizationBatchResult:
        source = self._source_reader.resolve_source(
            key=self.SOURCE_KEY,
            cutoff_date=cutoff_date,
        )
        file_name = source.path.name.strip()
        if not file_name:
            raise ValueError("credit XML resolved source file name is required")

        digest = self._source_reader.sha256(source.path)
        facts: list[CreditXMLRateRiskFact] = []
        exclusions: list[IRRBBSourceExclusion] = []
        failures: list[IRRBBSourceMappingFailure] = []
        seen_ids: set[str] = set()
        source_record_count = 0

        for raw_record in self._source_reader.iter_records(source):
            source_record_count += 1
            envelope = self._envelope(file_name=file_name, record=raw_record)
            if envelope.source_record_id in seen_ids:
                raise ValueError("credit XML source record lineage must be unique")
            seen_ids.add(envelope.source_record_id)

            outcome = self._normalizer.normalize(envelope, cutoff_date=cutoff_date)
            if isinstance(outcome, CreditXMLRateRiskFact):
                facts.append(outcome)
            elif isinstance(outcome, IRRBBSourceExclusion):
                exclusions.append(outcome)
            else:
                failures.append(outcome)

        return CreditXMLNormalizationBatchResult(
            cutoff_date=cutoff_date,
            source_file_name=file_name,
            source_sha256=digest,
            source_record_count=source_record_count,
            normalized_facts=tuple(facts),
            source_exclusions=tuple(exclusions),
            mapping_failures=tuple(failures),
        )

    @classmethod
    def _envelope(
        cls,
        *,
        file_name: str,
        record: XMLConfiaRecord,
    ) -> IRRBBSourceRecordEnvelope[XMLConfiaRecord]:
        record_id = record.record_id.strip()
        if not record_id:
            raise ValueError("credit XML Registro id is required")
        source_record_id = f"{cls.SOURCE_KIND}:{file_name}:record:{record_id}"
        source_reference = f"{cls.SOURCE_KIND}:{file_name}|record={record_id}"
        return IRRBBSourceRecordEnvelope(
            source_record_id=source_record_id,
            source_reference=source_reference,
            payload=record,
        )
