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
        _document(spec).replace(
            "<TipoMoneda>1</TipoMoneda>", "<TipoMoneda>2</TipoMoneda>"
        ),
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
