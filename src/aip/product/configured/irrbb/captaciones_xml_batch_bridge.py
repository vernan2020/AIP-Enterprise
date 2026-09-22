from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol

from aip.application.irrbb import IRRBBSourceMappingFailure
from aip.product.configured.irrbb.captaciones_xml_normalizer import (
    CaptacionesXMLFact,
    CaptacionesXMLNormalizer,
)
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.irrbb.xml_confia_source import (
    XMLConfiaRecord,
    XMLConfiaResolvedSource,
)


class CaptacionesXMLMonthlySourcePort(Protocol):
    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource: ...

    def iter_records(self, source: XMLConfiaResolvedSource) -> Iterable[XMLConfiaRecord]: ...

    def sha256(self, path: Path, *, chunk_size: int = 1024 * 1024) -> str: ...


@dataclass(frozen=True, slots=True)
class CaptacionesXMLNormalizationBatchResult:
    cutoff_date: date
    source_file_name: str
    source_sha256: str
    source_record_count: int
    normalized_facts: tuple[CaptacionesXMLFact, ...]
    mapping_failures: tuple[IRRBBSourceMappingFailure, ...]

    def __post_init__(self) -> None:
        if not self.source_file_name.strip():
            raise ValueError("Captaciones XML source_file_name is required")
        if len(self.source_sha256) != 64:
            raise ValueError("Captaciones XML source_sha256 must be a SHA-256 hex digest")
        try:
            int(self.source_sha256, 16)
        except ValueError as exc:
            raise ValueError("Captaciones XML source_sha256 must be hexadecimal") from exc
        if self.source_record_count < 0:
            raise ValueError("Captaciones XML source_record_count cannot be negative")
        if len(self.normalized_facts) + len(self.mapping_failures) != self.source_record_count:
            raise ValueError("every Captaciones XML record must have one normalization outcome")

        ids = tuple(item.source_record_id for item in self.normalized_facts) + tuple(
            item.source_record_id for item in self.mapping_failures
        )
        if len(ids) != len(set(ids)):
            raise ValueError("Captaciones XML outcomes must have unique source_record_id")


class CaptacionesXMLMonthlyNormalizationBridge:
    """Resolve and normalize Pasivos 210 without activating IRRBB classification."""

    SOURCE_KEY = "CAPTACIONES"
    SOURCE_KIND = "XML_CONFIA"

    def __init__(
        self,
        *,
        source_reader: CaptacionesXMLMonthlySourcePort,
        normalizer: CaptacionesXMLNormalizer | None = None,
    ) -> None:
        self._source_reader = source_reader
        self._normalizer = normalizer or CaptacionesXMLNormalizer()

    def normalize(self, *, cutoff_date: date) -> CaptacionesXMLNormalizationBatchResult:
        source = self._source_reader.resolve_source(
            key=self.SOURCE_KEY,
            cutoff_date=cutoff_date,
        )
        file_name = source.path.name.strip()
        if not file_name:
            raise ValueError("Captaciones XML resolved source file name is required")

        facts: list[CaptacionesXMLFact] = []
        failures: list[IRRBBSourceMappingFailure] = []
        seen_ids: set[str] = set()
        source_record_count = 0

        for raw_record in self._source_reader.iter_records(source):
            source_record_count += 1
            envelope = self._envelope(file_name=file_name, record=raw_record)
            if envelope.source_record_id in seen_ids:
                raise ValueError("Captaciones XML source record lineage must be unique")
            seen_ids.add(envelope.source_record_id)

            outcome = self._normalizer.normalize(envelope)
            if isinstance(outcome, CaptacionesXMLFact):
                facts.append(outcome)
            else:
                failures.append(outcome)

        return CaptacionesXMLNormalizationBatchResult(
            cutoff_date=cutoff_date,
            source_file_name=file_name,
            source_sha256=self._source_reader.sha256(source.path),
            source_record_count=source_record_count,
            normalized_facts=tuple(facts),
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
            raise ValueError("Captaciones XML Registro id is required")
        return IRRBBSourceRecordEnvelope(
            source_record_id=f"{cls.SOURCE_KIND}:{file_name}:record:{record_id}",
            source_reference=f"{cls.SOURCE_KIND}:{file_name}|record={record_id}",
            payload=record,
        )
