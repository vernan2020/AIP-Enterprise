from __future__ import annotations

from datetime import date
from pathlib import Path

from aip.product.configured.irrbb.regulatory_financial_xml import (
    REGULATORY_XML_SPECS,
    RegulatoryFinancialXMLReader,
)


def _month(tmp_path: Path) -> Path:
    month = tmp_path / "2026" / "09-SEPTIEMBRE"
    month.mkdir(parents=True)
    return month


def _document(
    spec,
    *,
    total: str = "150.00",
    detail: tuple[str, str] = ("100", "50"),
    period: str = "01/09/2026",
    entity: str = "3004045138",
    action: str = "insertar",
) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ArchivoSICVECA>
  <Encabezado>
    <ClaseDato>22</ClaseDato>
    <Archivo>2201</Archivo>
    <Periodo>{period}</Periodo>
    <IdEntidad>{entity}</IdEntidad>
    <TipoCarga>1</TipoCarga>
    <TipoMoneda>1</TipoMoneda>
  </Encabezado>
  <Datos>
    <Registro id="1" accion="{action}">
      <{spec.account_field}>101</{spec.account_field}>
      <TipoCatalogoSUGEF>{spec.catalog_code}</TipoCatalogoSUGEF>
      <{spec.bucket_field}>1</{spec.bucket_field}>
      <{spec.amount_field}>{detail[0]}</{spec.amount_field}>
    </Registro>
    <Registro id="2" accion="insertar">
      <{spec.account_field}>101</{spec.account_field}>
      <TipoCatalogoSUGEF>{spec.catalog_code}</TipoCatalogoSUGEF>
      <{spec.bucket_field}>2</{spec.bucket_field}>
      <{spec.amount_field}>{detail[1]}</{spec.amount_field}>
    </Registro>
    <RegistroTotal id="3" accion="insertar">
      <{spec.account_field}>101</{spec.account_field}>
      <TipoCatalogoSUGEF>{spec.catalog_code}</TipoCatalogoSUGEF>
      <{spec.total_field}>{total}</{spec.total_field}>
    </RegistroTotal>
  </Datos>
</ArchivoSICVECA>
"""


def _write_pair(month: Path, **overrides) -> None:
    for spec in REGULATORY_XML_SPECS:
        (month / spec.filename).write_text(_document(spec, **overrides), encoding="utf-8")


def test_reads_existing_year_month_folder_and_reconciles_regulatory_totals(tmp_path: Path) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    result = RegulatoryFinancialXMLReader(str(tmp_path)).load(cutoff_date=date(2026, 9, 30))
    assert result.is_valid
    assert {item.key for item in result.files} == {"BRECHAS", "CALCE"}
    for item in result.files:
        assert item.status == "VALIDATED"
        assert item.period == date(2026, 9, 1)
        assert item.entity_id == "3004045138"
        assert len(item.rows) == 2
        assert len(item.account_totals) == 1
        assert sum(x.amount for x in item.rows) == item.account_totals[0].amount
        assert len(item.source_sha256 or "") == 64


def test_totals_are_not_double_counted_and_a_mismatch_fails_closed(tmp_path: Path) -> None:
    month = _month(tmp_path)
    _write_pair(month, total="151.00")
    result = RegulatoryFinancialXMLReader(str(tmp_path)).load(cutoff_date=date(2026, 9, 30))
    assert not result.is_valid
    assert all(item.status == "BLOCKED" for item in result.files)
    assert all("no concilia" in item.issues[0] for item in result.files)
    assert all(item.rows == () for item in result.files)


def test_missing_files_and_incorrect_month_are_not_treated_as_zero(tmp_path: Path) -> None:
    reader = RegulatoryFinancialXMLReader(str(tmp_path))
    missing = reader.load(cutoff_date=date(2026, 9, 30))
    assert not missing.is_valid
    assert all(item.status == "MISSING" for item in missing.files)
    month = _month(tmp_path)
    _write_pair(month, period="01/08/2026")
    mismatched = reader.load(cutoff_date=date(2026, 9, 30))
    assert not mismatched.is_valid
    assert all(item.status == "BLOCKED" for item in mismatched.files)
    assert all("Periodo" in item.issues[0] for item in mismatched.files)


def test_different_entities_in_same_month_block_the_pair(tmp_path: Path) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    calce = REGULATORY_XML_SPECS[1]
    (month / calce.filename).write_text(_document(calce, entity="OTHER"), encoding="utf-8")
    result = RegulatoryFinancialXMLReader(str(tmp_path)).load(cutoff_date=date(2026, 9, 30))
    assert not result.is_valid
    assert all(item.status == "BLOCKED" for item in result.files)
    assert all("entidades diferentes" in item.issues[0] for item in result.files)


def test_catalog_code_invalid_actions_and_unsafe_declarations_fail_closed(
    tmp_path: Path,
) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    spec = REGULATORY_XML_SPECS[0]
    path = month / spec.filename
    path.write_text(
        _document(spec).replace(
            "<TipoCatalogoSUGEF>5</TipoCatalogoSUGEF>",
            "<TipoCatalogoSUGEF>4</TipoCatalogoSUGEF>",
        ),
        encoding="utf-8",
    )
    reader = RegulatoryFinancialXMLReader(str(tmp_path))
    result = reader.load(cutoff_date=date(2026, 9, 30))
    assert result.files[0].status == "BLOCKED"
    assert "Catálogo incorrecto" in result.files[0].issues[0]

    path.write_text(_document(spec, action="eliminar"), encoding="utf-8")
    result = reader.load(cutoff_date=date(2026, 9, 30))
    assert "no soportada" in result.files[0].issues[0]

    path.write_text(
        '<!DOCTYPE ArchivoSICVECA [<!ENTITY x "XX">]>' + _document(spec),
        encoding="utf-8",
    )
    result = reader.load(cutoff_date=date(2026, 9, 30))
    assert result.files[0].status == "BLOCKED"
    assert "DTD/ENTITY" in result.files[0].issues[0]


def test_regulatory_header_rejects_non_crc_currency_and_wrong_data_class(
    tmp_path: Path,
) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    spec = REGULATORY_XML_SPECS[0]
    path = month / spec.filename
    path.write_text(
        _document(spec).replace("<TipoMoneda>1</TipoMoneda>", "<TipoMoneda>2</TipoMoneda>"),
        encoding="utf-8",
    )
    reader = RegulatoryFinancialXMLReader(str(tmp_path))
    result = reader.load(cutoff_date=date(2026, 9, 30))
    assert not result.is_valid
    assert result.files[0].status == "BLOCKED"
    assert "TipoMoneda inválido" in result.files[0].issues[0]

    path.write_text(
        _document(spec).replace("<ClaseDato>22</ClaseDato>", "<ClaseDato>17</ClaseDato>"),
        encoding="utf-8",
    )
    result = reader.load(cutoff_date=date(2026, 9, 30))
    assert result.files[0].status == "BLOCKED"
    assert "ClaseDato diferente" in result.files[0].issues[0]


def test_regulatory_file_accepts_resend_type_without_losing_audit_metadata(tmp_path: Path):
    month = _month(tmp_path)
    _write_pair(month)
    for spec in REGULATORY_XML_SPECS:
        path = month / spec.filename
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "<TipoCarga>1</TipoCarga>", "<TipoCarga>2</TipoCarga>"
            ),
            encoding="utf-8",
        )
    snapshot = RegulatoryFinancialXMLReader(str(tmp_path)).load(cutoff_date=date(2026, 9, 30))
    assert snapshot.is_valid
    assert all(item.load_type == "2" for item in snapshot.files)


def test_latest_prefers_newest_reported_month_not_filesystem_timestamp(tmp_path: Path) -> None:
    september = _month(tmp_path)
    _write_pair(september)
    october = tmp_path / "2026" / "10-OCTUBRE"
    october.mkdir()
    for spec in REGULATORY_XML_SPECS:
        (october / spec.filename).write_text(
            _document(spec, period="01/10/2026"),
            encoding="utf-8",
        )

    snapshot = RegulatoryFinancialXMLReader(str(tmp_path)).load_latest(
        reference_cutoff=date(2026, 9, 30)
    )
    assert snapshot.is_valid
    assert snapshot.cutoff_date == date(2026, 10, 1)
    assert all(item.period == date(2026, 10, 1) for item in snapshot.files)


def test_newest_partial_month_never_falls_back_to_an_older_valid_pair(
    tmp_path: Path,
) -> None:
    september = _month(tmp_path)
    _write_pair(september)
    october = tmp_path / "2026" / "10-OCTUBRE"
    october.mkdir()
    spec = REGULATORY_XML_SPECS[0]
    (october / spec.filename).write_text(
        _document(spec, period="01/10/2026"),
        encoding="utf-8",
    )

    snapshot = RegulatoryFinancialXMLReader(str(tmp_path)).load_latest(
        reference_cutoff=date(2026, 10, 12)
    )
    assert snapshot.cutoff_date == date(2026, 10, 1)
    assert not snapshot.is_valid
    assert snapshot.files[0].status == "VALIDATED"
    assert snapshot.files[1].status == "BLOCKED"
    assert "encontrados: 0" in snapshot.files[1].issues[0]


def test_latest_fails_closed_if_newest_reported_period_is_wrong(
    tmp_path: Path,
) -> None:
    september = _month(tmp_path)
    _write_pair(september)
    october = tmp_path / "2026" / "10-OCTUBRE"
    october.mkdir()
    for spec in REGULATORY_XML_SPECS:
        (october / spec.filename).write_text(
            _document(spec, period="01/09/2026"),
            encoding="utf-8",
        )

    snapshot = RegulatoryFinancialXMLReader(str(tmp_path)).load_latest(
        reference_cutoff=date(2026, 10, 12)
    )
    assert snapshot.cutoff_date == date(2026, 10, 1)
    assert all(item.status == "BLOCKED" for item in snapshot.files)
    assert all("Periodo" in item.issues[0] for item in snapshot.files)


def test_latest_without_any_regulatory_files_is_missing_not_zero(tmp_path: Path) -> None:
    month = _month(tmp_path)
    (month / "Other_Contable.xml").write_text("<ignored/>", encoding="utf-8")

    snapshot = RegulatoryFinancialXMLReader(str(tmp_path)).load_latest(
        reference_cutoff=date(2026, 10, 12)
    )
    assert snapshot.cutoff_date == date(2026, 10, 12)
    assert all(item.status == "MISSING" for item in snapshot.files)
    assert not snapshot.is_valid


def test_sicveca_padded_xml_tag_names_match_real_institutional_export(
    tmp_path: Path,
) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    spec = REGULATORY_XML_SPECS[0]
    path = month / spec.filename
    content = _document(spec)
    for field in (
        "CuentaBrecha",
        "RangoBrecha",
        "MontoBrecha",
    ):
        content = content.replace(f"<{field}>", f"<{field} >")
        content = content.replace(f"</{field}>", f"</{field} >")
    path.write_text(content, encoding="utf-8")

    result = RegulatoryFinancialXMLReader(str(tmp_path)).load(cutoff_date=date(2026, 9, 30))
    assert result.is_valid
    assert len(result.files[0].rows) == 2
    assert result.files[0].account_totals[0].amount == sum(
        row.amount for row in result.files[0].rows
    )



def test_reader_blocks_xml_modified_during_import(
    tmp_path: Path, monkeypatch,
) -> None:
    month = _month(tmp_path)
    _write_pair(month)
    reader = RegulatoryFinancialXMLReader(str(tmp_path))
    real_checksum = reader._monthly.sha256
    calls: dict[str, int] = {}

    def unstable_checksum(path: Path) -> str:
        count = calls.get(path.name, 0) + 1
        calls[path.name] = count
        if path.name == REGULATORY_XML_SPECS[0].filename and count == 2:
            return "0" * 64
        return real_checksum(path)

    monkeypatch.setattr(reader._monthly, "sha256", unstable_checksum)
    result = reader.load(cutoff_date=date(2026, 9, 30))

    assert not result.is_valid
    assert result.files[0].status == "BLOCKED"
    assert "cambió durante la lectura" in result.files[0].issues[0]
