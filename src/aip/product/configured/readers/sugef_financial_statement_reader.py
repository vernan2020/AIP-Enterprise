from __future__ import annotations

import csv
import hashlib
import importlib.resources as resources
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
from aip.product.configured.readers.sugef_financial_api_client import (
    SUGEFFinancialApiClient,
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
    _REFERENCE_PACKAGE = "aip.product.demo.data"
    _REFERENCE_FILE = "sugef_indicators_july_2026.csv"
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
            "NOMBRE ENTIDAD FINANCIERA",
            "DESCRIPCION ENTIDAD",
        ),
        "category": ("TIPO ENTIDAD", "CATEGORIA", "SECTOR", "GRUPO ENTIDAD"),
        "statement_date": (
            "FECHA",
            "FECHA CORTE",
            "FECHA DE CORTE",
            "FECHA INFORMACION",
            "FECHA DE INFORMACION",
            "PERIODO",
            "MES",
        ),
        "statement_type": (
            "ESTADO FINANCIERO",
            "TIPO ESTADO",
            "TIPO DE ESTADO",
            "REPORTE",
        ),
        "account_code": (
            "CUENTA",
            "NUMERO CUENTA",
            "NUMERO DE CUENTA",
            "CODIGO CUENTA",
            "CODIGO DE CUENTA",
            "CODIGO",
        ),
        "account_name": (
            "DESCRIPCION",
            "DESCRIPCION CUENTA",
            "NOMBRE CUENTA",
            "CUENTA CONTABLE",
            "CONCEPTO",
            "NOMBRE",
            "DETALLE CUENTA",
        ),
        "amount": (
            "SALDO",
            "SALDO TOTAL",
            "SALDO REPORTADO",
            "MONTO",
            "VALOR",
            "SALDO COLONES",
            "MONTO COLONES",
        ),
        "currency": ("MONEDA", "CODIGO MONEDA"),
    }
    _REQUIRED = frozenset(("entity_name", "statement_date", "account_name", "amount"))

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFFinancialApiClient | None = None,
    ) -> None:
        self._config = config
        self._api_client = api_client or SUGEFFinancialApiClient(config)

    def read(self, *, cutoff_date: date | None = None) -> SUGEFFinancialReadResult:
        configured_paths = self._discover_files()
        paths = configured_paths
        diagnostics: list[str] = []
        lines: list[FinancialStatementLine] = []
        api_endpoints: tuple[str, ...] = ()
        if self._config.enabled and self._config.api_enabled and cutoff_date is not None:
            api_result = self._api_client.read(cutoff_date)
            lines.extend(api_result.lines)
            api_endpoints = api_result.endpoints
            diagnostics.extend(api_result.diagnostics)
        for path in paths:
            try:
                lines.extend(self._read_file(path, diagnostics))
            except Exception as exc:
                diagnostics.append(f"{path.name}: no se pudo leer ({type(exc).__name__}: {exc})")
        if lines and api_endpoints:
            # The bundled official matrix supplies peer indicators while the REST API
            # supplies the selected institutions' authoritative accounting balances.
            reference = self._reference_file()
            if reference is not None:
                reference_lines = self._read_file(reference, diagnostics)
                live_entities = {
                    self._entity_match_key(line.entity.name): line.entity for line in lines
                }
                live_accounts = {
                    (
                        self._entity_match_key(line.entity.name),
                        line.statement_type,
                        self._normalize(line.account_name),
                    )
                    for line in lines
                }
                live_date = max(line.statement_date for line in lines)
                for reference_line in reference_lines:
                    entity_key = self._entity_match_key(reference_line.entity.name)
                    account_key = (
                        entity_key,
                        reference_line.statement_type,
                        self._normalize(reference_line.account_name),
                    )
                    if account_key in live_accounts:
                        continue
                    lines.append(
                        self._with_context(
                            reference_line,
                            statement_date=live_date,
                            entity=live_entities.get(entity_key, reference_line.entity),
                        )
                    )
                paths = (*paths, reference)
                diagnostics.append(
                    "Los pares comparables provienen de la matriz institucional; "
                    "los saldos de la entidad consultada provienen de la API SUGEF."
                )
        elif not lines:
            reference = self._reference_file()
            if reference is not None:
                paths = (reference,)
                lines.extend(self._read_file(reference, diagnostics))
                diagnostics.append(
                    "Mostrando la matriz institucional de referencia de julio 2026; "
                    "use Actualizar fuente cuando agregue una exportación SUGEF más reciente."
                )
        if not configured_paths and self._config.root and not api_endpoints:
            diagnostics.append(
                "No se encontraron exportaciones SUGEF compatibles en la ruta configurada."
            )
        elif not configured_paths and not self._config.root and not api_endpoints:
            diagnostics.append(
                "Ruta SUGEF local no configurada; se activó la referencia institucional incluida."
            )
        if self._config.download_endpoint is None and configured_paths:
            diagnostics.append(
                "La actualización utiliza las exportaciones oficiales disponibles en la ruta configurada."
            )
        return SUGEFFinancialReadResult(
            lines=tuple(lines),
            source_files=(*api_endpoints, *(str(path) for path in paths)),
            diagnostics=tuple(diagnostics),
            fingerprint=self._fingerprint(paths, cutoff_date=cutoff_date),
        )

    def fingerprint(self, *, cutoff_date: date | None = None) -> str:
        paths = self._discover_files()
        if not paths:
            reference = self._reference_file()
            paths = (reference,) if reference is not None else ()
        return self._fingerprint(paths, cutoff_date=cutoff_date)

    @staticmethod
    def _with_context(
        line: FinancialStatementLine,
        *,
        statement_date: date,
        entity: FinancialEntity,
    ) -> FinancialStatementLine:
        return FinancialStatementLine(
            entity=entity,
            statement_date=statement_date,
            statement_type=line.statement_type,
            account_code=line.account_code,
            account_name=line.account_name,
            amount=line.amount,
            currency=line.currency,
            trace=line.trace,
        )

    @classmethod
    def _entity_match_key(cls, name: str) -> str:
        normalized = cls._normalize(name)
        for token in ("COOPEALIANZA", "COOPEANDE"):
            if token in normalized:
                return token
        return normalized

    @classmethod
    def _reference_file(cls) -> Path | None:
        try:
            resource = resources.files(cls._REFERENCE_PACKAGE).joinpath(cls._REFERENCE_FILE)
            if resource.is_file():
                return Path(str(resource))
        except (ModuleNotFoundError, OSError, TypeError):
            return None
        return None

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
    def _fingerprint(paths: tuple[Path, ...], *, cutoff_date: date | None = None) -> str:
        digest = hashlib.sha256()
        digest.update(str(cutoff_date or "").encode("ascii"))
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            digest.update(str(path).encode("utf-8"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
        return digest.hexdigest()
