from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
    XMLConfiaSourceConfig,
)
from aip.product.configured.irrbb.xml_confia_source import (
    XML_CONFIA_SOURCE_STEMS,
    XMLConfiaMonthlySourceReader,
)


def _xml(*, periodo: str = "01/08/2026", archivo: str = "2701") -> str:
    return f"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<ArchivoSICVECA>
  <Encabezado>
    <ClaseDato>27</ClaseDato>
    <VersionClaseDato>1.0</VersionClaseDato>
    <Archivo>{archivo}</Archivo>
    <VersionArchivo>1.0</VersionArchivo>
    <Periodo>{periodo}</Periodo>
    <IdEntidad>3004045138</IdEntidad>
    <TipoCarga>1</TipoCarga>
    <TipoMoneda>1</TipoMoneda>
  </Encabezado>
  <Datos>
    <Registro id="1" accion="insertar">
      <IdOperacion>OP-1</IdOperacion>
      <TipoMonedaObligacion>2</TipoMonedaObligacion>
      <SaldoPrincipal>100.25</SaldoPrincipal>
    </Registro>
    <Registro id="2" accion="insertar">
      <IdOperacion>OP-2</IdOperacion>
      <SaldoPrincipal>50</SaldoPrincipal>
    </Registro>
  </Datos>
</ArchivoSICVECA>
"""


def _month_dir(tmp_path: Path) -> Path:
    month = tmp_path / "2026" / "08-AGOSTO"
    month.mkdir(parents=True)
    return month


def test_resolves_governed_month_and_required_source_names(tmp_path: Path) -> None:
    month = _month_dir(tmp_path)
    for key, stem in XML_CONFIA_SOURCE_STEMS.items():
        archivo = {
            "CREDIT": "5103",
            "CAPTACIONES": "2702",
            "BORROWING": "2701",
            "BORROWING_MATURITY": "2703",
            "INVESTMENT": "9999",
        }[key]
        (month / f"{stem}.xml").write_text(_xml(archivo=archivo), encoding="latin-1")

    reader = XMLConfiaMonthlySourceReader(str(tmp_path))
    sources = reader.resolve_required_sources(date(2026, 8, 31))

    assert tuple(source.key for source in sources) == tuple(XML_CONFIA_SOURCE_STEMS)
    assert {source.path.parent.name for source in sources} == {"08-AGOSTO"}
    assert all(source.header.periodo == date(2026, 8, 1) for source in sources)


def test_record_iteration_preserves_source_values_without_semantic_inference(
    tmp_path: Path,
) -> None:
    month = _month_dir(tmp_path)
    path = month / "Pasivos_Cuentas_Contables_220_230_260_270_280.xml"
    path.write_text(_xml(), encoding="latin-1")

    reader = XMLConfiaMonthlySourceReader(str(tmp_path))
    source = reader.resolve_source(key="BORROWING", cutoff_date=date(2026, 8, 31))

    rows = tuple(reader.iter_records(source))

    assert len(rows) == 2
    assert rows[0].record_id == "1"
    assert rows[0].action == "insertar"
    assert rows[0].values == {
        "IdOperacion": "OP-1",
        "TipoMonedaObligacion": "2",
        "SaldoPrincipal": "100.25",
    }
    assert rows[1].values["IdOperacion"] == "OP-2"


def test_period_must_match_requested_cutoff_month(tmp_path: Path) -> None:
    month = _month_dir(tmp_path)
    path = month / "Pasivos_Cuentas_Contables_210.xml"
    path.write_text(_xml(periodo="01/07/2026"), encoding="latin-1")

    reader = XMLConfiaMonthlySourceReader(str(tmp_path))

    with pytest.raises(ValueError, match="Periodo does not match requested cutoff month"):
        reader.resolve_source(key="CAPTACIONES", cutoff_date=date(2026, 8, 31))


def test_missing_and_duplicate_governed_source_files_fail_closed(tmp_path: Path) -> None:
    month = _month_dir(tmp_path)
    reader = XMLConfiaMonthlySourceReader(str(tmp_path))

    with pytest.raises(FileNotFoundError, match="required XML CONFÍA source"):
        reader.resolve_source(key="CREDIT", cutoff_date=date(2026, 8, 31))

    stem = XML_CONFIA_SOURCE_STEMS["CREDIT"]
    (month / f"{stem}.xml").write_text(_xml(), encoding="latin-1")
    (month / f"{stem.upper()}.XML").write_text(_xml(), encoding="latin-1")

    with pytest.raises(ValueError, match="multiple XML CONFÍA files"):
        reader.resolve_source(key="CREDIT", cutoff_date=date(2026, 8, 31))


def test_sha256_is_stable_and_streamed_from_source_bytes(tmp_path: Path) -> None:
    path = tmp_path / "source.xml"
    payload = _xml().encode("latin-1")
    path.write_bytes(payload)

    assert XMLConfiaMonthlySourceReader.sha256(path) == hashlib.sha256(payload).hexdigest()


def test_xml_confia_configuration_round_trips_without_hardcoded_user_path() -> None:
    config = ConfiguredSourceConfig(
        xml_confia=XMLConfiaSourceConfig(
            enabled=True,
            root=r"%USERPROFILE%\OneDrive - COOPEALIANZA R.L\XML CONFÍA",
        )
    )

    safe = config.to_safe_dict()
    rebuilt = ConfiguredSourceConfig.from_safe_dict(safe)

    assert rebuilt.xml_confia.enabled is True
    assert rebuilt.xml_confia.root == config.xml_confia.root
    assert "RMESEN" not in rebuilt.xml_confia.root
    assert safe["xml_confia"]["enabled"] is True
