from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from aip.application.irrbb.contracts import IRRBBSourceSnapshot
from aip.application.irrbb.source_certification import IRRBBSourceCertificationReport
from aip.product.configured.irrbb.investment_master_mapper import (
    InvestmentMasterSourcePayload,
)
from aip.product.configured.irrbb.investment_source_evidence import (
    InvestmentMasterSourceEvidenceAssessor,
)
from aip.product.configured.irrbb.source_acl import (
    IRRBBCanonicalPositionMapper,
    IRRBBSourceRecordEnvelope,
    IRRBBSourceSnapshotAssembler,
)
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)


@dataclass(frozen=True, slots=True)
class InvestmentMasterBatchBridgeResult:
    """Auditable result of one institutional investment-master bridge execution."""

    requested_cutoff_date: date
    source_record_count: int
    reader_rejected_row_count: int
    source_warnings: tuple[str, ...]
    certification: IRRBBSourceCertificationReport
    snapshot: IRRBBSourceSnapshot

    def __post_init__(self) -> None:
        if self.source_record_count < 0:
            raise ValueError("source_record_count cannot be negative")
        if self.reader_rejected_row_count < 0:
            raise ValueError("reader_rejected_row_count cannot be negative")
        if self.snapshot.cutoff_date != self.requested_cutoff_date:
            raise ValueError("snapshot cutoff must match the requested cutoff")
        represented = len(self.snapshot.position_records) + len(self.snapshot.mapping_failures)
        if represented != self.source_record_count:
            raise ValueError("every prepared source record must be represented in the snapshot")


class InstitutionalInvestmentMasterEnvelopeFactory:
    """Create source envelopes while preserving reader-level file/sheet/row lineage."""

    SOURCE_KIND = "INSTITUTIONAL_PORTFOLIO_MASTER"

    @classmethod
    def build(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> tuple[IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload], ...]:
        if not result.normalized_positions:
            return ()

        file_name = Path(result.source_file).name if result.source_file else ""
        sheet_name = result.sheet_selected.strip()
        if not file_name:
            raise ValueError("investment master source_file is required when positions exist")
        if not sheet_name:
            raise ValueError("investment master sheet_selected is required when positions exist")

        envelopes: list[IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload]] = []
        source_record_ids: set[str] = set()
        for position in result.normalized_positions:
            source_row = cls._source_row(position.get("source_row"))
            source_record_id = cls._source_record_id(
                file_name=file_name,
                sheet_name=sheet_name,
                source_row=source_row,
            )
            if source_record_id in source_record_ids:
                raise ValueError("investment master source-row lineage must be unique")
            source_record_ids.add(source_record_id)

            source_reference = cls._source_reference(
                file_name=file_name,
                sheet_name=sheet_name,
                source_row=source_row,
            )
            envelopes.append(
                IRRBBSourceRecordEnvelope(
                    source_record_id=source_record_id,
                    source_reference=source_reference,
                    payload=InvestmentMasterSourcePayload(
                        normalized_position=dict(position),
                        detected_column_mapping=dict(result.detected_column_mapping),
                    ),
                )
            )
        return tuple(envelopes)

    @classmethod
    def batch_source_reference(
        cls,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> str | None:
        if not result.source_file:
            return None
        file_name = Path(result.source_file).name
        if not file_name:
            return None
        sheet_name = result.sheet_selected.strip()
        if sheet_name:
            return f"{cls.SOURCE_KIND}:{file_name}|sheet={sheet_name}"
        return f"{cls.SOURCE_KIND}:{file_name}"

    @staticmethod
    def _source_row(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                "investment master source_row must be a positive integer supplied by the reader"
            )
        return value

    @classmethod
    def _source_record_id(
        cls,
        *,
        file_name: str,
        sheet_name: str,
        source_row: int,
    ) -> str:
        return f"{cls.SOURCE_KIND}:{file_name}:sheet:{sheet_name}:row:{source_row}"

    @classmethod
    def _source_reference(
        cls,
        *,
        file_name: str,
        sheet_name: str,
        source_row: int,
    ) -> str:
        return f"{cls.SOURCE_KIND}:{file_name}|sheet={sheet_name}|row={source_row}"


class InstitutionalInvestmentMasterBatchBridge:
    """Connect investment source evidence, certification gate and canonical mapper.

    The bridge deliberately does not upgrade source evidence. It uses the Phase 12
    evidence assessor exactly as certified and delegates the mandatory Phase 13
    gate to ``IRRBBSourceSnapshotAssembler``. Consequently, the Phase 14 mapper is
    not invoked while the current investment source certification remains non-ready.
    """

    def __init__(
        self,
        mapper: IRRBBCanonicalPositionMapper[InvestmentMasterSourcePayload],
    ) -> None:
        self._assembler = IRRBBSourceSnapshotAssembler(mapper)

    def assemble(
        self,
        *,
        cutoff_date: date,
        result: InstitutionalPortfolioMasterReadResult,
    ) -> InvestmentMasterBatchBridgeResult:
        source_records = InstitutionalInvestmentMasterEnvelopeFactory.build(result)
        certification = InvestmentMasterSourceEvidenceAssessor.assess(result)
        batch_reference = InstitutionalInvestmentMasterEnvelopeFactory.batch_source_reference(
            result
        )
        source_references = (batch_reference,) if batch_reference is not None else ()
        snapshot = self._assembler.assemble(
            cutoff_date=cutoff_date,
            source_records=source_records,
            source_certification=certification,
            source_references=source_references,
        )
        return InvestmentMasterBatchBridgeResult(
            requested_cutoff_date=cutoff_date,
            source_record_count=len(source_records),
            reader_rejected_row_count=result.rejected_row_count,
            source_warnings=result.warnings,
            certification=certification,
            snapshot=snapshot,
        )
