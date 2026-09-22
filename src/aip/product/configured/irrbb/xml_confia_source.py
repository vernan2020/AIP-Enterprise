from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree

from aip.product.configured.configuration.institutional_paths import build_institutional_path

_XML_MONTH_NAMES = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}

XML_CONFIA_SOURCE_STEMS = {
    "CREDIT": "NEC2024_Operaciones_5103",
    "CAPTACIONES": "Pasivos_Cuentas_Contables_210",
    "BORROWING": "Pasivos_Cuentas_Contables_220_230_260_270_280",
    "BORROWING_MATURITY": "Pasivos_Tabla_Vencimiento_Obligaciones",
    "INVESTMENT": "Crediticio_InversionesActivas",
}


@dataclass(frozen=True, slots=True)
class XMLConfiaHeader:
    clase_dato: str
    archivo: str
    periodo: date
    id_entidad: str
    tipo_carga: str
    tipo_moneda: str


@dataclass(frozen=True, slots=True)
class XMLConfiaRecord:
    record_id: str
    action: str
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class XMLConfiaResolvedSource:
    key: str
    path: Path
    header: XMLConfiaHeader


class XMLConfiaMonthlySourceReader:
    """Resolve and stream governed XML CONFÍA monthly source files.

    The reader owns physical discovery and source-shape preservation only. It does
    not interpret product semantics or map rows into canonical IRRBB positions.
    """

    def __init__(self, root: str) -> None:
        if not root.strip():
            raise ValueError("XML CONFÍA root is required")
        self._root = root

    def resolve_month_directory(self, cutoff_date: date) -> Path:
        month_folder = f"{cutoff_date.month:02d}-{_XML_MONTH_NAMES[cutoff_date.month]}"
        resolved = build_institutional_path(
            str(cutoff_date.year),
            month_folder,
            base_root=self._root,
        )
        if resolved is None:
            raise ValueError("could not resolve XML CONFÍA month directory")
        path = Path(resolved)
        if not path.is_dir():
            raise FileNotFoundError(f"XML CONFÍA month directory not found: {path}")
        return path

    def resolve_source(self, *, key: str, cutoff_date: date) -> XMLConfiaResolvedSource:
        try:
            stem = XML_CONFIA_SOURCE_STEMS[key]
        except KeyError as exc:
            raise KeyError(f"unsupported XML CONFÍA source key: {key}") from exc

        month_directory = self.resolve_month_directory(cutoff_date)
        source_path = self._find_exact_stem(month_directory, stem)
        header = self.read_header(source_path)
        self._validate_period(header=header, cutoff_date=cutoff_date, path=source_path)
        return XMLConfiaResolvedSource(key=key, path=source_path, header=header)

    def resolve_required_sources(self, cutoff_date: date) -> tuple[XMLConfiaResolvedSource, ...]:
        return tuple(
            self.resolve_source(key=key, cutoff_date=cutoff_date)
            for key in XML_CONFIA_SOURCE_STEMS
        )

    def read_header(self, path: Path) -> XMLConfiaHeader:
        values: dict[str, str] = {}
        for event, element in ElementTree.iterparse(path, events=("end",)):
            if element.tag == "Encabezado":
                for child in element:
                    values[child.tag] = (child.text or "").strip()
                element.clear()
                break
            element.clear()

        required = ("ClaseDato", "Archivo", "Periodo", "IdEntidad", "TipoCarga", "TipoMoneda")
        missing = tuple(name for name in required if not values.get(name))
        if missing:
            raise ValueError(f"XML CONFÍA header missing required fields: {','.join(missing)}")

        try:
            periodo = datetime.strptime(values["Periodo"], "%d/%m/%Y").date()
        except ValueError as exc:
            raise ValueError("XML CONFÍA Periodo must use DD/MM/YYYY") from exc

        return XMLConfiaHeader(
            clase_dato=values["ClaseDato"],
            archivo=values["Archivo"],
            periodo=periodo,
            id_entidad=values["IdEntidad"],
            tipo_carga=values["TipoCarga"],
            tipo_moneda=values["TipoMoneda"],
        )

    def iter_records(self, source: XMLConfiaResolvedSource) -> Iterator[XMLConfiaRecord]:
        for event, element in ElementTree.iterparse(source.path, events=("end",)):
            if element.tag != "Registro":
                continue
            values = {
                child.tag.strip(): (child.text or "").strip()
                for child in element
            }
            yield XMLConfiaRecord(
                record_id=(element.attrib.get("id") or "").strip(),
                action=(element.attrib.get("accion") or "").strip(),
                values=values,
            )
            element.clear()

    @staticmethod
    def sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _find_exact_stem(month_directory: Path, stem: str) -> Path:
        candidates = tuple(
            item
            for item in month_directory.iterdir()
            if item.is_file()
            and item.suffix.casefold() == ".xml"
            and item.stem.casefold() == stem.casefold()
        )
        if not candidates:
            raise FileNotFoundError(
                f"required XML CONFÍA source {stem}.xml not found in {month_directory}"
            )
        if len(candidates) > 1:
            raise ValueError(
                f"multiple XML CONFÍA files match governed source stem {stem}: "
                + ", ".join(sorted(item.name for item in candidates))
            )
        return candidates[0]

    @staticmethod
    def _validate_period(
        *,
        header: XMLConfiaHeader,
        cutoff_date: date,
        path: Path,
    ) -> None:
        if (header.periodo.year, header.periodo.month) != (
            cutoff_date.year,
            cutoff_date.month,
        ):
            raise ValueError(
                "XML CONFÍA Periodo does not match requested cutoff month: "
                f"{path.name}={header.periodo.isoformat()} cutoff={cutoff_date.isoformat()}"
            )
