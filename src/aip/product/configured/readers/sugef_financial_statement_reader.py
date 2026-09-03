from __future__ import annotations

import csv
import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

import openpyxl
import xlrd

from aip.domain.financial_analysis.models import (
    FinancialEntity,
    FinancialStatementLine,
    FinancialStatementType,
    SourceTrace,
)
from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)


@dataclass(frozen=True, slots=True)
class SUGEFFinancialReadResult:
    lines: tuple[FinancialStatementLine, ...]
    source_files: tuple[str, ...]
    diagnostics: tuple[str, ...]
    fingerprint: str


class SUGEFFinancialStatementReader:
    """Lee exportaciones oficiales sin acoplar el dominio al diseño de cada archivo."""

    _SOURCE_NAME = "SUGEF - Información Financiera Contable"
    _ALIASES = {
        "entity_id": (
            "CODIGO ENTIDAD",
            "CODIGO DE ENTIDAD",
            "ID ENTIDAD",
            "IDENTIFICACION ENTIDAD",
        ),
        "entity_name": (
            "ENTIDAD",
            "NOMBRE ENTIDAD",
            "NOMBRE DE ENTIDAD",
            "ENTIDAD FINANCIERA",
        ),
        "category": ("TIPO ENTIDAD", "CATEGORIA", "SECTOR", "GRUPO ENTIDAD"),
        "statement_date": ("FECHA", "FECHA CORTE", "FECHA DE CORTE", "PERIODO"),
        "statement_type": (
            "ESTADO FINANCIERO",
            "TIPO ESTADO",
            "TIPO DE ESTADO",
            "REPORTE",
        ),
        "account_code": ("CUENTA", "CODIGO CUENTA", "CODIGO DE CUENTA", "CODIGO"),
        "account_name": (
            "DESCRIPCION",
            "DESCRIPCION CUENTA",
            "NOMBRE CUENTA",
            "CUENTA CONTABLE",
            "CONCEPTO",
        ),
        "amount": ("SALDO", "MONTO", "VALOR", "SALDO COLONES", "MONTO COLONES"),
        "currency": ("MONEDA", "CODIGO MONEDA"),
    }
    _REQUIRED = frozenset(("entity_name", "statement_date", "account_name", "amount"))

    def __init__(self, config: SUGEFFinancialSourceConfig) -> None:
        self._config = config

    def read(self) -> SUGEFFinancialReadResult:
        paths = self._discover_files()
        diagnostics: list[str] = []
        lines: list[FinancialStatementLine] = []
        for path in paths:
            try:
                lines.extend(self._read_file(path, diagnostics))
            except Exception as exc:
                diagnostics.append(f"{path.name}: no se pudo leer ({type(exc).__name__}: {exc})")
        if not self._config.enabled:
            diagnostics.append("Fuente SUGEF desactivada: configure AIP_SUGEF_FINANCIAL_ROOT.")
        elif not paths:
            diagnostics.append("No se encontraron exportaciones SUGEF compatibles en la ruta configurada.")
        if self._config.download_endpoint is None:
            diagnostics.append(
                "Descarga automática pendiente de validación; la ingesta utiliza exportaciones oficiales."
            )
        return SUGEFFinancialReadResult(
            lines=tuple(lines),
            source_files=tuple(str(path) for path in paths),
            diagnostics=tuple(diagnostics),
            fingerprint=self._fingerprint(paths),
        )

    def fingerprint(self) -> str:
        return self._fingerprint(self._discover_files())

    def _discover_files(self) -> tuple[Path, ...]:
        if not self._config.enabled or not self._config.root:
            return ()
        root = Path(self._config.root)
        if not root.exists() or not root.is_dir():
            return ()
        iterator = root.rglob(self._config.file_pattern) if self._config.recursive else root.glob(
            self._config.file_pattern
        )
        extensions = {value.lower() for value in self._config.supported_extensions}
        try:
            files = [
                path
                for path in iterator
                if path.is_file()
                and path.suffix.lower() in extensions
                and not path.name.startswith("~$")
            ]
        except OSError:
            return ()
        return tuple(sorted(files, key=lambda item: str(item).casefold()))

    def _read_file(
        self, path: Path, diagnostics: list[str]
    ) -> list[FinancialStatementLine]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._read_csv(path, diagnostics)
        if suffix == ".xlsx":
            return self._read_xlsx(path, diagnostics)
        if suffix == ".xls":
            return self._read_xls(path, diagnostics)
        return []

    def _read_csv(
        self, path: Path, diagnostics: list[str]
    ) -> list[FinancialStatementLine]:
        raw = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(raw[:8192], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(raw.splitlines(), dialect=dialect))
        return self._parse_rows(path, "CSV", rows, diagnostics)

    def _read_xlsx(
        self, path: Path, diagnostics: list[str]
    ) -> list[FinancialStatementLine]:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        result: list[FinancialStatementLine] = []
        try:
            for sheet in workbook.worksheets:
                rows = (tuple(cell for cell in row) for row in sheet.iter_rows(values_only=True))
                result.extend(self._parse_rows(path, sheet.title, rows, diagnostics))
        finally:
            workbook.close()
        return result

    def _read_xls(
        self, path: Path, diagnostics: list[str]
    ) -> list[FinancialStatementLine]:
        workbook = xlrd.open_workbook(path, on_demand=True)
        result: list[FinancialStatementLine] = []
        try:
            for sheet in workbook.sheets():
                rows = (tuple(sheet.row_values(index)) for index in range(sheet.nrows))
                result.extend(self._parse_rows(path, sheet.name, rows, diagnostics))
        finally:
            workbook.release_resources()
        return result

    def _parse_rows(
        self,
        path: Path,
        sheet_name: str,
        rows: Iterable[tuple[Any, ...] | list[Any]],
        diagnostics: list[str],
    ) -> list[FinancialStatementLine]:
        buffered: list[tuple[Any, ...]] = []
        iterator = iter(rows)
        header_index = -1
        mapping: dict[str, int] = {}
        for index in range(40):
            try:
                row = tuple(next(iterator))
            except StopIteration:
                break
            buffered.append(row)
            candidate = self._header_mapping(row)
            if self._REQUIRED.issubset(candidate):
                header_index = index
                mapping = candidate
                break
        if header_index < 0:
            if any(any(self._text(value) for value in row) for row in buffered):
                diagnostics.append(
                    f"{path.name}/{sheet_name}: encabezados SUGEF no reconocidos; hoja omitida."
                )
            return []

        result: list[FinancialStatementLine] = []
        for row_number, row in enumerate(iterator, start=header_index + 2):
            values = tuple(row)
            entity_name = self._field(values, mapping, "entity_name")
            statement_date = self._date(self._raw_field(values, mapping, "statement_date"))
            account_name = self._field(values, mapping, "account_name")
            amount = self._decimal(self._raw_field(values, mapping, "amount"))
            if not entity_name or statement_date is None or not account_name or amount is None:
                continue
            entity_id = self._field(values, mapping, "entity_id") or self._entity_id(entity_name)
            entity = FinancialEntity(
                entity_id=entity_id,
                name=entity_name,
                category=self._field(values, mapping, "category") or "Sin clasificar",
            )
            statement_hint = self._field(values, mapping, "statement_type")
            result.append(
                FinancialStatementLine(
                    entity=entity,
                    statement_date=statement_date,
                    statement_type=self._statement_type(statement_hint or sheet_name or path.stem),
                    account_code=self._field(values, mapping, "account_code"),
                    account_name=account_name,
                    amount=amount,
                    currency=self._currency(self._field(values, mapping, "currency")),
                    trace=SourceTrace(
                        source_name=self._SOURCE_NAME,
                        source_url=self._config.official_information_url,
                        file_path=str(path),
                        sheet_name=sheet_name,
                        row_number=row_number,
                    ),
                )
            )
        return result

    @classmethod
    def _header_mapping(cls, row: tuple[Any, ...]) -> dict[str, int]:
        result: dict[str, int] = {}
        aliases = {key: set(values) for key, values in cls._ALIASES.items()}
        for index, value in enumerate(row):
            normalized = cls._normalize(cls._text(value))
            for key, choices in aliases.items():
                if normalized in choices and key not in result:
                    result[key] = index
        return result

    @staticmethod
    def _raw_field(row: tuple[Any, ...], mapping: dict[str, int], key: str) -> Any:
        index = mapping.get(key)
        return row[index] if index is not None and index < len(row) else None

    @classmethod
    def _field(cls, row: tuple[Any, ...], mapping: dict[str, int], key: str) -> str:
        return cls._text(cls._raw_field(row, mapping, key))

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @classmethod
    def _normalize(cls, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        plain = "".join(char for char in decomposed if not unicodedata.combining(char))
        return " ".join(plain.upper().replace("_", " ").split())

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            try:
                return xlrd.xldate_as_datetime(float(value), 0).date()
            except (ValueError, OverflowError):
                return None
        text = str(value or "").strip()
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d", "%m/%Y"):
            try:
                parsed = datetime.strptime(text, pattern).date()
                if pattern == "%m/%Y":
                    return date(parsed.year, parsed.month, 1)
                return parsed
            except ValueError:
                continue
        return None

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        text = str(value).strip().replace("₡", "").replace("$", "").replace(" ", "")
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        if "," in text and "." in text:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif "," in text:
            tail = text.rsplit(",", 1)[-1]
            text = text.replace(",", ".") if len(tail) <= 2 else text.replace(",", "")
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return None
        return -parsed if negative else parsed

    @classmethod
    def _statement_type(cls, value: str) -> FinancialStatementType:
        normalized = cls._normalize(value)
        if "RESULTADO" in normalized:
            return FinancialStatementType.INCOME_STATEMENT
        if "BALANCE" in normalized or "SITUACION" in normalized:
            return FinancialStatementType.BALANCE_SHEET
        if "INDICADOR" in normalized:
            return FinancialStatementType.INDICATORS
        if "COMPROBACION" in normalized:
            return FinancialStatementType.TRIAL_BALANCE
        return FinancialStatementType.UNKNOWN

    @staticmethod
    def _currency(value: str) -> str:
        normalized = value.upper().strip()
        if normalized in {"USD", "DOLAR", "DOLARES", "$"}:
            return "USD"
        return "CRC"

    @classmethod
    def _entity_id(cls, name: str) -> str:
        normalized = cls._normalize(name)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        return f"SUGEF-{digest}"

    @staticmethod
    def _fingerprint(paths: tuple[Path, ...]) -> str:
        digest = hashlib.sha256()
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            digest.update(str(path).encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
        return digest.hexdigest()
