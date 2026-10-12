from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

from aip.product.configured.irrbb.xml_confia_source import XMLConfiaMonthlySourceReader


@dataclass(frozen=True, slots=True)
class RegulatoryXMLSpec:
    key: str
    filename: str
    account_field: str
    bucket_field: str
    amount_field: str
    total_field: str
    catalog_code: str


REGULATORY_XML_SPECS = (
    RegulatoryXMLSpec(
        "BRECHAS",
        "Contable_Brecha.xml",
        "CuentaBrecha",
        "RangoBrecha",
        "MontoBrecha",
        "MontoTotalBrecha",
        "5",
    ),
    RegulatoryXMLSpec(
        "CALCE",
        "Contable_CalcePlazo.xml",
        "CuentaCalcePlazo",
        "RangoCalcePlazo",
        "MontoCalcePlazo",
        "MontoTotalCuenta",
        "4",
    ),
)


@dataclass(frozen=True, slots=True)
class RegulatoryXMLRow:
    record_id: str
    account_code: str
    catalog_code: str
    bucket_code: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class RegulatoryXMLAccountTotal:
    record_id: str
    account_code: str
    catalog_code: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class RegulatoryXMLFileResult:
    key: str
    filename: str
    status: str
    period: date | None = None
    entity_id: str | None = None
    reporting_currency_code: str | None = None
    load_type: str | None = None
    source_sha256: str | None = None
    rows: tuple[RegulatoryXMLRow, ...] = ()
    account_totals: tuple[RegulatoryXMLAccountTotal, ...] = ()
    issues: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.status == "VALIDATED"


@dataclass(frozen=True, slots=True)
class RegulatoryXMLPairResult:
    cutoff_date: date
    files: tuple[RegulatoryXMLFileResult, ...]

    @property
    def is_valid(self) -> bool:
        return len(self.files) == len(REGULATORY_XML_SPECS) and all(
            item.is_valid for item in self.files
        )


class RegulatoryFinancialXMLReader:
    """Read SICVECA FINANCIERO Brechas and Calce from the EXISTING XML CONFÍA root.

    These are regulatory account/bucket aggregates, not contractual banking-book
    positions or dated flows. NEVER feed them into EVE/NII position gateways.
    The input files remain untouched and a SHA-256 is retained for audit.
    """

    def __init__(self, root: str) -> None:
        self._monthly = XMLConfiaMonthlySourceReader(root)

    def load(self, *, cutoff_date: date) -> RegulatoryXMLPairResult:
        try:
            directory = self._monthly.resolve_month_directory(cutoff_date)
        except (OSError, ValueError) as exc:
            files = tuple(
                RegulatoryXMLFileResult(
                    key=spec.key,
                    filename=spec.filename,
                    status="MISSING",
                    issues=(str(exc),),
                )
                for spec in REGULATORY_XML_SPECS
            )
            return RegulatoryXMLPairResult(cutoff_date, files)

        files = tuple(self._load_one(directory, spec, cutoff_date) for spec in REGULATORY_XML_SPECS)
        if all(item.is_valid for item in files):
            first, second = files
            if first.entity_id != second.entity_id:
                files = tuple(
                    self._block(item, "Los XML corresponden a entidades diferentes.")
                    for item in files
                )
            elif first.reporting_currency_code != second.reporting_currency_code:
                files = tuple(
                    self._block(item, "TipoMoneda del encabezado no coincide entre archivos.")
                    for item in files
                )
        return RegulatoryXMLPairResult(cutoff_date, files)

    @staticmethod
    def _block(item: RegulatoryXMLFileResult, reason: str) -> RegulatoryXMLFileResult:
        return RegulatoryXMLFileResult(
            key=item.key,
            filename=item.filename,
            status="BLOCKED",
            period=item.period,
            entity_id=item.entity_id,
            reporting_currency_code=item.reporting_currency_code,
            load_type=item.load_type,
            source_sha256=item.source_sha256,
            issues=item.issues + (reason,),
        )

    def _load_one(
        self, directory: Path, spec: RegulatoryXMLSpec, cutoff_date: date
    ) -> RegulatoryXMLFileResult:
        try:
            matches = [
                path
                for path in directory.iterdir()
                if path.is_file() and path.name.casefold() == spec.filename.casefold()
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Se esperaba un solo {spec.filename}; encontrados: {len(matches)}"
                )
            path = matches[0]
            self._reject_unsafe_declarations(path)
            header = self._monthly.read_header(path)
            if header.clase_dato != "22":
                raise ValueError("ClaseDato diferente de 22 (Información Financiera).")
            if not header.tipo_carga.isascii() or not header.tipo_carga.isdigit() or len(header.tipo_carga) > 2:
                raise ValueError("TipoCarga regulatorio debe ser un código numérico.")
            if header.tipo_moneda != "1":
                raise ValueError("TipoMoneda inválido: Brechas y Calce deben reportar colones.")
            if (header.periodo.year, header.periodo.month) != (cutoff_date.year, cutoff_date.month):
                raise ValueError("El Periodo del XML no coincide con el mes de corte.")
            checksum = self._monthly.sha256(path)
            rows, totals = self._parse(path, spec)
            issues = self._reconcile(rows, totals)
            return RegulatoryXMLFileResult(
                key=spec.key,
                filename=path.name,
                status="BLOCKED" if issues else "VALIDATED",
                period=header.periodo,
                entity_id=header.id_entidad,
                reporting_currency_code=header.tipo_moneda,
                load_type=header.tipo_carga,
                source_sha256=checksum,
                rows=rows if not issues else (),
                account_totals=totals if not issues else (),
                issues=tuple(issues),
            )
        except (OSError, ValueError, StopIteration, ElementTree.ParseError) as exc:
            return RegulatoryXMLFileResult(
                key=spec.key,
                filename=spec.filename,
                status="BLOCKED",
                issues=(str(exc),),
            )

    @staticmethod
    def _reject_unsafe_declarations(path: Path) -> None:
        # The financial XML contract never needs DTDs/entities. Reject them
        # before ElementTree parses source-controlled content.
        needle_tail = b""
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                check = (needle_tail + chunk).upper()
                if b"<!DOCTYPE" in check or b"<!ENTITY" in check:
                    raise ValueError("XML con declaración DTD/ENTITY no permitida.")
                needle_tail = check[-10:]

    @classmethod
    def _parse(
        cls, path: Path, spec: RegulatoryXMLSpec
    ) -> tuple[tuple[RegulatoryXMLRow, ...], tuple[RegulatoryXMLAccountTotal, ...]]:
        cls._reject_unsafe_declarations(path)
        context = ElementTree.iterparse(path, events=("start", "end"))
        event, root = next(context)
        if event != "start" or root.tag != "ArchivoSICVECA":
            raise ValueError("La raíz del XML debe ser ArchivoSICVECA.")
        rows: list[RegulatoryXMLRow] = []
        totals: list[RegulatoryXMLAccountTotal] = []
        row_ids: set[str] = set()
        total_ids: set[str] = set()
        for event, element in context:
            if event != "end" or element.tag not in ("Registro", "RegistroTotal"):
                continue
            record_id = (element.get("id") or "").strip()
            action = (element.get("accion") or "").strip().lower()
            ids = row_ids if element.tag == "Registro" else total_ids
            if not record_id or record_id in ids:
                raise ValueError(f"ID ausente o repetido en {element.tag}.")
            ids.add(record_id)
            # Modifications/deletions require an explicit incremental-merge policy.
            if action != "insertar":
                raise ValueError(
                    f"Acción XML {action or '(vacía)'} no soportada sin conciliación incremental."
                )
            values = {child.tag: (child.text or "").strip() for child in element}
            account_key = spec.account_field
            catalog = cls._digits(values, "TipoCatalogoSUGEF")
            if catalog != spec.catalog_code:
                raise ValueError(
                    f"Catálogo incorrecto en {spec.key}: {catalog}; esperado {spec.catalog_code}."
                )
            account = cls._digits(values, account_key)
            if element.tag == "Registro":
                bucket = cls._digits(values, spec.bucket_field)
                amount = cls._amount(values, spec.amount_field)
                rows.append(RegulatoryXMLRow(record_id, account, catalog, bucket, amount))
            else:
                amount = cls._amount(values, spec.total_field)
                totals.append(RegulatoryXMLAccountTotal(record_id, account, catalog, amount))
            element.clear()
            root.clear()
        return tuple(rows), tuple(totals)

    @staticmethod
    def _digits(values: dict[str, str], field: str) -> str:
        value = values.get(field, "")
        if not value or not value.isascii() or not value.isdigit():
            raise ValueError(f"Campo numérico requerido inválido: {field}")
        return value

    @staticmethod
    def _amount(values: dict[str, str], field: str) -> Decimal:
        raw = values.get(field, "").strip()
        if not raw or "," in raw:
            raise ValueError(f"Monto numérico requerido inválido: {field}")
        try:
            amount = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"Monto numérico requerido inválido: {field}") from exc
        if not amount.is_finite() or amount.as_tuple().exponent < -2:
            raise ValueError(f"Monto inválido o de más de dos decimales: {field}")
        return amount

    @staticmethod
    def _reconcile(
        rows: tuple[RegulatoryXMLRow, ...],
        totals: tuple[RegulatoryXMLAccountTotal, ...],
    ) -> list[str]:
        issues: list[str] = []
        if not rows:
            issues.append("No hay registros de detalle.")
        if not totals:
            issues.append("No hay RegistroTotal para conciliar.")
        actual: dict[str, Decimal] = defaultdict(Decimal)
        unique_buckets: set[tuple[str, str]] = set()
        for row in rows:
            key = (row.account_code, row.bucket_code)
            if key in unique_buckets:
                issues.append(f"Cuenta/banda duplicada: {key[0]} / {key[1]}")
            unique_buckets.add(key)
            actual[row.account_code] += row.amount
        seen_totals: set[str] = set()
        for total in totals:
            account = total.account_code
            if account in seen_totals:
                issues.append(f"Total de cuenta duplicado: {account}")
            seen_totals.add(account)
            if account not in actual:
                issues.append(f"Total sin detalle: {account}")
            elif abs(actual[account] - total.amount) > Decimal("0.01"):
                issues.append(f"Total no concilia para cuenta {account}.")
        for account in actual.keys() - seen_totals:
            issues.append(f"Cuenta sin RegistroTotal: {account}")
        return issues
