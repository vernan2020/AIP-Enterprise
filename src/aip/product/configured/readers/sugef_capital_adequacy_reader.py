from __future__ import annotations

import io
import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


@dataclass(frozen=True, slots=True)
class SUGEFCapitalAdequacyReadResult:
    lines: tuple[FinancialStatementLine, ...]
    source_cutoff: date | None
    source_files: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _DownloadLink:
    href: str
    text: str
    cutoff: date


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


class SUGEFCapitalAdequacyReader:
    """Lee la suficiencia patrimonial trimestral publicada por SUGEF.

    El valor trimestral se lleva al corte contable solicitado únicamente para
    efectos de calificación, preservando en la trazabilidad la fecha oficial del
    dato. No se interpola ni se recalcula entre publicaciones trimestrales.
    """

    SOURCE_PAGE = "https://www.sugef.fi.cr/reportes/Suficiencia%20Patrimonial.aspx"
    _MONTHS = {
        "ENERO": 1,
        "FEBRERO": 2,
        "MARZO": 3,
        "ABRIL": 4,
        "MAYO": 5,
        "JUNIO": 6,
        "JULIO": 7,
        "AGOSTO": 8,
        "SETIEMBRE": 9,
        "SEPTIEMBRE": 9,
        "OCTUBRE": 10,
        "NOVIEMBRE": 11,
        "DICIEMBRE": 12,
    }

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFPublicApiClient | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
    ) -> None:
        self._config = config
        self._api = api_client or SUGEFPublicApiClient(config)
        self._fetch_bytes = fetch_bytes or self._download

    def read(self, cutoff_date: date) -> SUGEFCapitalAdequacyReadResult:
        try:
            page = self._fetch_bytes(self.SOURCE_PAGE).decode("utf-8", errors="replace")
            links = self._discover_links(page)
            selected = next((link for link in links if link.cutoff <= cutoff_date), None)
            if selected is None:
                return SUGEFCapitalAdequacyReadResult(
                    (),
                    None,
                    (),
                    ("Suficiencia Patrimonial SUGEF: no existe un corte trimestral previo.",),
                )
            workbook_url = urljoin(self.SOURCE_PAGE, selected.href)
            workbook_bytes = self._fetch_bytes(workbook_url)
            entity_index = self._entity_index()
            lines, diagnostics = self._read_workbook(
                workbook_bytes,
                workbook_url=workbook_url,
                source_cutoff=selected.cutoff,
                analysis_cutoff=cutoff_date,
                entity_index=entity_index,
            )
            diagnostics.insert(
                0,
                "Suficiencia Patrimonial SUGEF: último corte trimestral oficial aplicable "
                f"{selected.cutoff:%d/%m/%Y}; usado para el análisis {cutoff_date:%d/%m/%Y}.",
            )
            return SUGEFCapitalAdequacyReadResult(
                lines=lines,
                source_cutoff=selected.cutoff,
                source_files=(workbook_url,),
                diagnostics=tuple(diagnostics),
            )
        except (
            OSError,
            ValueError,
            KeyError,
            InvalidOperation,
            BadZipFile,
            InvalidFileException,
        ) as exc:
            return SUGEFCapitalAdequacyReadResult(
                (),
                None,
                (),
                (f"Suficiencia Patrimonial SUGEF: {type(exc).__name__}: {exc}",),
            )

    def _entity_index(self) -> dict[str, FinancialEntity]:
        response = self._api.list_entities()
        index: dict[str, FinancialEntity] = {}
        for row in response.rows:
            entity_id = self._text(row.get("codigoEntidad"))
            name = self._text(row.get("nombreEntidad")) or self._text(
                row.get("aliasPublicacionEntidad")
            )
            if not entity_id or not name:
                continue
            entity = FinancialEntity(
                entity_id=entity_id,
                name=name,
                category=self._text(row.get("descripcionSector")) or "Sin clasificar",
            )
            aliases = {
                name,
                self._text(row.get("aliasEntidad")),
                self._text(row.get("aliasPublicacionEntidad")),
            }
            for alias in aliases:
                if alias:
                    index[self._normalize(alias)] = entity
        return index

    @classmethod
    def _discover_links(cls, page: str) -> tuple[_DownloadLink, ...]:
        parser = _LinkParser()
        parser.feed(page)
        links: list[_DownloadLink] = []
        for href, text in parser.links:
            if ".xlsx" not in href.lower():
                continue
            cutoff = cls._cutoff_from_text(f"{text} {href}")
            if cutoff is None:
                continue
            links.append(_DownloadLink(href=href, text=text, cutoff=cutoff))
        return tuple(sorted(links, key=lambda item: item.cutoff, reverse=True))

    @classmethod
    def _cutoff_from_text(cls, value: str) -> date | None:
        normalized = cls._normalize(value)
        for month_name, month in cls._MONTHS.items():
            match = re.search(rf"\b{month_name}\b\D*(20\d{{2}})", normalized)
            if match:
                year = int(match.group(1))
                return date(year, month, monthrange(year, month)[1])
        return None

    @classmethod
    def _read_workbook(
        cls,
        payload: bytes,
        *,
        workbook_url: str,
        source_cutoff: date,
        analysis_cutoff: date,
        entity_index: dict[str, FinancialEntity],
    ) -> tuple[tuple[FinancialStatementLine, ...], list[str]]:
        workbook = load_workbook(io.BytesIO(payload), data_only=True, read_only=True)
        output: list[FinancialStatementLine] = []
        diagnostics: list[str] = []
        unresolved: set[str] = set()
        try:
            for sheet in workbook.worksheets:
                rows = list(sheet.iter_rows(values_only=True))
                header = cls._header(rows)
                if header is None:
                    continue
                header_row, entity_column, value_column = header
                for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
                    if entity_column >= len(row) or value_column >= len(row):
                        continue
                    entity_name = cls._text(row[entity_column])
                    value = cls._decimal(row[value_column])
                    if not entity_name or value is None:
                        continue
                    entity = entity_index.get(cls._normalize(entity_name))
                    if entity is None:
                        unresolved.add(entity_name)
                        continue
                    ratio = value / Decimal("100") if abs(value) > Decimal("1") else value
                    output.append(
                        FinancialStatementLine(
                            entity=entity,
                            statement_date=analysis_cutoff,
                            statement_type=FinancialStatementType.INDICATORS,
                            account_code="SUGEF:CAPITAL_ADEQUACY",
                            account_name="Suficiencia Patrimonial",
                            amount=ratio,
                            currency="RATIO",
                            trace=SourceTrace(
                                source_name="SUGEF · Suficiencia Patrimonial trimestral",
                                source_url=workbook_url,
                                file_path=f"corte oficial {source_cutoff:%d/%m/%Y}",
                                sheet_name=sheet.title,
                                row_number=row_number,
                            ),
                        )
                    )
        finally:
            workbook.close()
        if unresolved:
            diagnostics.append(
                "Suficiencia Patrimonial SUGEF: entidades sin correspondencia exacta en "
                f"catálogo oficial: {', '.join(sorted(unresolved))}."
            )
        if not output:
            diagnostics.append(
                "Suficiencia Patrimonial SUGEF: el XLSX no produjo indicadores utilizables."
            )
        else:
            diagnostics.append(
                f"Suficiencia Patrimonial SUGEF: {len(output)} entidades cargadas desde XLSX."
            )
        return tuple(output), diagnostics

    @classmethod
    def _header(cls, rows: list[tuple[Any, ...]]) -> tuple[int, int, int] | None:
        for row_index, row in enumerate(rows[:30]):
            normalized = [cls._normalize(cls._text(value)) for value in row]
            value_candidates = [
                index
                for index, value in enumerate(normalized)
                if "SUFICIENCIA PATRIMONIAL" in value
            ]
            entity_candidates = [
                index
                for index, value in enumerate(normalized)
                if value
                in {
                    "ENTIDAD",
                    "NOMBRE ENTIDAD",
                    "NOMBRE DE LA ENTIDAD",
                    "ALIAS ENTIDAD",
                }
            ]
            if value_candidates and entity_candidates:
                return row_index, entity_candidates[0], value_candidates[0]
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, str):
            text = value.strip().replace("%", "").replace(",", ".")
        else:
            text = str(value)
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )

    @staticmethod
    def _download(url: str) -> bytes:
        request = Request(
            url,
            headers={
                "User-Agent": "AIP-Enterprise/1.0 SUGEF public-data reader",
                "Accept": "text/html,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
            },
        )
        with urlopen(request, timeout=90) as response:
            return response.read()
