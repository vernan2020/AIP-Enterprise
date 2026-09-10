from __future__ import annotations

from datetime import date

import pytest

from aip.application.irrbb.contracts import (
    IRRBBPositionSourceRecord,
    IRRBBSourceMappingFailure,
    IRRBBSourceMappingFailureCode,
)
from aip.application.irrbb.source_certification import IRRBBSourceCertificationStatus
from aip.product.configured.irrbb.investment_master_batch_bridge import (
    InstitutionalInvestmentMasterBatchBridge,
    InstitutionalInvestmentMasterEnvelopeFactory,
)
from aip.product.configured.irrbb.investment_master_mapper import InvestmentMasterSourcePayload
from aip.product.configured.irrbb.source_acl import IRRBBSourceRecordEnvelope
from aip.product.configured.readers.institutional_portfolio_master_reader import (
    InstitutionalPortfolioMasterReadResult,
)


def _mapping() -> dict[str, str]:
    return {
        "contract_number": "Numero Contrato",
        "currency": "Moneda",
        "maturity_date": "Fecha Vencimiento",
        "product_code": "Codigo Producto",
        "classification": "Clasificacion",
        "series": "Serie",
        "isin": "ISIN",
        "principal_balance": "Saldo Principal",
        "book_value": "Saldo Valor Compra",
        "nominal_rate": "Tasa Nominal",
        "periodicity": "Periodicidad",
        "last_interest_payment_date": "Fecha Ultimo Pago Intereses",
        "variable_rate_flag": "Indicador Tasa Variable",
    }


def _position(*, source_row: object = 7) -> dict[str, object]:
    return {
        "source_row": source_row,
        "contract_number": "C-100",
        "currency": "CRC",
        "maturity_date": date(2028, 7, 31),
        "product_code": "TP",
        "classification": "FVOCI",
        "series": "SER-100",
        "isin": "CR0000000100",
        "principal_balance": 1_000_000.0,
        "book_value": 995_000.0,
        "nominal_rate": 6.25,
        "periodicity": "semestral",
        "last_interest_payment_date": date(2026, 7, 31),
        "variable_rate_flag": "N",
        "source_values": {
            "numero contrato": "C-100",
            "moneda": "CRC",
            "fecha vencimiento": "2028-07-31",
            "codigo producto": "TP",
            "clasificacion": "FVOCI",
            "serie": "SER-100",
            "isin": "CR0000000100",
            "saldo principal": "1000000",
            "saldo valor compra": "995000",
            "tasa nominal": "6.25",
            "periodicidad": "semestral",
            "fecha ultimo pago intereses": "2026-07-31",
            "indicador tasa variable": "N",
        },
    }


def _read_result(
    *,
    positions: list[dict[str, object]] | None = None,
    valuation_date: date = date(2026, 7, 31),
    rejected_row_count: int = 0,
    warnings: tuple[str, ...] = (),
) -> InstitutionalPortfolioMasterReadResult:
    return InstitutionalPortfolioMasterReadResult(
        source_file=r"C:\Institutional\2026\maestro\julio\maestro_31-07-2026.xlsx",
        valuation_date=valuation_date,
        sheet_selected="Maestro",
        normalized_positions=positions if positions is not None else [_position()],
        warnings=warnings,
        rejected_row_count=rejected_row_count,
        source_status="HEALTHY" if not warnings and rejected_row_count == 0 else "DEGRADED",
        detected_column_mapping=_mapping(),
        diagnostics={},
    )


class _SpyMapper:
    def __init__(self) -> None:
        self.calls = 0

    def map_record(
        self,
        record: IRRBBSourceRecordEnvelope[InvestmentMasterSourcePayload],
    ) -> IRRBBPositionSourceRecord | IRRBBSourceMappingFailure:
        self.calls += 1
        return IRRBBSourceMappingFailure(
            source_record_id=record.source_record_id,
            source_reference=record.source_reference,
            code=IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED,
            canonical_field=None,
            message="spy mapper should not have been called",
        )


def test_envelope_factory_preserves_file_sheet_row_lineage_without_path_leakage() -> None:
    result = _read_result()

    records = InstitutionalInvestmentMasterEnvelopeFactory.build(result)

    assert len(records) == 1
    record = records[0]
    assert record.source_record_id.endswith(":sheet:Maestro:row:7")
    assert record.source_reference == (
        "INSTITUTIONAL_PORTFOLIO_MASTER:maestro_31-07-2026.xlsx|sheet=Maestro|row=7"
    )
    assert "C:\\Institutional" not in record.source_reference
    assert record.payload.normalized_position["contract_number"] == "C-100"
    assert record.payload.detected_column_mapping["currency"] == "Moneda"


def test_non_ready_phase12_certification_rejects_batch_before_mapper_invocation() -> None:
    mapper = _SpyMapper()
    bridge = InstitutionalInvestmentMasterBatchBridge(mapper)

    output = bridge.assemble(cutoff_date=date(2026, 7, 31), result=_read_result())

    assert output.certification.status is IRRBBSourceCertificationStatus.INCOMPLETE
    assert mapper.calls == 0
    assert output.source_record_count == 1
    assert output.snapshot.position_records == ()
    assert len(output.snapshot.mapping_failures) == 1
    failure = output.snapshot.mapping_failures[0]
    assert failure.code is IRRBBSourceMappingFailureCode.SOURCE_RECORD_REJECTED
    assert failure.source_record_id.endswith(":sheet:Maestro:row:7")
    assert failure.source_reference.endswith("|sheet=Maestro|row=7")
    assert "INV-CUTOFF-DATE" in failure.message
    assert "INV-INSTRUMENT-CLASS" in failure.message
    assert "INV-SIDE" in failure.message
    assert "INV-PAYMENT-STRUCTURE" in failure.message
    assert "INV-OPTIONALITY" in failure.message


def test_requested_cutoff_is_snapshot_context_not_source_cutoff_evidence() -> None:
    mapper = _SpyMapper()
    bridge = InstitutionalInvestmentMasterBatchBridge(mapper)
    result = _read_result(valuation_date=date(2026, 7, 31))

    output = bridge.assemble(cutoff_date=date(2026, 8, 31), result=result)

    assert output.snapshot.cutoff_date == date(2026, 8, 31)
    assert output.requested_cutoff_date == date(2026, 8, 31)
    assert "INV-CUTOFF-DATE" in output.certification.not_assessed_requirement_ids
    assert mapper.calls == 0


def test_reader_rejection_and_warning_metadata_are_retained_explicitly() -> None:
    mapper = _SpyMapper()
    bridge = InstitutionalInvestmentMasterBatchBridge(mapper)
    result = _read_result(
        rejected_row_count=2,
        warnings=("Rejected row 9: malformed position",),
    )

    output = bridge.assemble(cutoff_date=date(2026, 7, 31), result=result)

    assert output.reader_rejected_row_count == 2
    assert output.source_warnings == ("Rejected row 9: malformed position",)
    assert output.source_record_count == 1
    assert mapper.calls == 0


def test_envelope_factory_rejects_missing_or_non_integer_reader_row_lineage() -> None:
    for invalid_row in (None, "7", 0, -1, True):
        with pytest.raises(ValueError, match="source_row must be a positive integer"):
            InstitutionalInvestmentMasterEnvelopeFactory.build(
                _read_result(positions=[_position(source_row=invalid_row)])
            )


def test_envelope_factory_rejects_duplicate_source_row_lineage() -> None:
    with pytest.raises(ValueError, match="source-row lineage must be unique"):
        InstitutionalInvestmentMasterEnvelopeFactory.build(
            _read_result(positions=[_position(source_row=7), _position(source_row=7)])
        )


def test_positions_require_source_file_and_sheet_lineage() -> None:
    missing_file = _read_result()
    missing_file = InstitutionalPortfolioMasterReadResult(
        source_file="",
        valuation_date=missing_file.valuation_date,
        sheet_selected=missing_file.sheet_selected,
        normalized_positions=missing_file.normalized_positions,
        warnings=missing_file.warnings,
        rejected_row_count=missing_file.rejected_row_count,
        source_status=missing_file.source_status,
        detected_column_mapping=missing_file.detected_column_mapping,
        diagnostics=missing_file.diagnostics,
    )
    with pytest.raises(ValueError, match="source_file is required"):
        InstitutionalInvestmentMasterEnvelopeFactory.build(missing_file)

    missing_sheet = _read_result()
    missing_sheet = InstitutionalPortfolioMasterReadResult(
        source_file=missing_sheet.source_file,
        valuation_date=missing_sheet.valuation_date,
        sheet_selected=" ",
        normalized_positions=missing_sheet.normalized_positions,
        warnings=missing_sheet.warnings,
        rejected_row_count=missing_sheet.rejected_row_count,
        source_status=missing_sheet.source_status,
        detected_column_mapping=missing_sheet.detected_column_mapping,
        diagnostics=missing_sheet.diagnostics,
    )
    with pytest.raises(ValueError, match="sheet_selected is required"):
        InstitutionalInvestmentMasterEnvelopeFactory.build(missing_sheet)


def test_empty_reader_result_produces_empty_non_ready_snapshot_without_mapper_calls() -> None:
    mapper = _SpyMapper()
    bridge = InstitutionalInvestmentMasterBatchBridge(mapper)
    result = _read_result(positions=[])

    output = bridge.assemble(cutoff_date=date(2026, 7, 31), result=result)

    assert output.source_record_count == 0
    assert output.snapshot.position_records == ()
    assert output.snapshot.mapping_failures == ()
    assert output.certification.is_ready is False
    assert mapper.calls == 0
