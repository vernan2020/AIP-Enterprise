from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.error import HTTPError, URLError

from aip.product.configured.configuration.configured_source_config import (
    SUGEFFinancialSourceConfig,
)
from aip.product.configured.readers.sugef_public_api_client import SUGEFPublicApiClient


@dataclass(frozen=True, slots=True)
class SUGEFAccountCatalogEntry:
    account_code: str
    catalog_type_code: str
    catalog_type_name: str
    parent_account_code: str | None
    account_name: str
    level: Decimal | None
    sign: int | None


@dataclass(frozen=True, slots=True)
class SUGEFAccountCatalogReadResult:
    entries: tuple[SUGEFAccountCatalogEntry, ...]
    endpoint: str | None
    diagnostics: tuple[str, ...]


class SUGEFAccountCatalogReader:
    """Normaliza el catálogo contable oficial publicado por la API SUGEF.

    Los códigos se conservan como texto para no perder ceros significativos.
    Los campos nulos permanecen nulos; nunca se transforman en cero.
    """

    def __init__(
        self,
        config: SUGEFFinancialSourceConfig,
        *,
        api_client: SUGEFPublicApiClient | None = None,
    ) -> None:
        self._api = api_client or SUGEFPublicApiClient(config)

    def read(self) -> SUGEFAccountCatalogReadResult:
        try:
            response = self._api.list_account_catalog()
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            return SUGEFAccountCatalogReadResult(
                entries=(),
                endpoint=None,
                diagnostics=(f"SUGEF API catálogo contable: {type(exc).__name__}: {exc}",),
            )

        entries: list[SUGEFAccountCatalogEntry] = []
        skipped = 0
        for row in response.rows:
            entry = self._normalize(row)
            if entry is None:
                skipped += 1
                continue
            entries.append(entry)
        diagnostics = [
            f"Catálogo contable SUGEF: {len(entries)} cuentas normalizadas desde API oficial."
        ]
        if skipped:
            diagnostics.append(
                f"Catálogo contable SUGEF: {skipped} filas omitidas por falta de código, "
                "tipo de catálogo o nombre de cuenta; no se imputaron valores."
            )
        return SUGEFAccountCatalogReadResult(
            entries=tuple(entries),
            endpoint=response.endpoint,
            diagnostics=tuple(diagnostics),
        )

    @classmethod
    def find_candidates(
        cls,
        entries: tuple[SUGEFAccountCatalogEntry, ...],
        *terms: str,
        catalog_type_code: str | None = None,
    ) -> tuple[SUGEFAccountCatalogEntry, ...]:
        """Busca candidatos por nombre sin decidir automáticamente una cuenta."""

        normalized_terms = tuple(cls._normalize_text(term) for term in terms if term.strip())
        if not normalized_terms:
            return ()
        candidates = []
        for entry in entries:
            if catalog_type_code is not None and entry.catalog_type_code != catalog_type_code:
                continue
            name = cls._normalize_text(entry.account_name)
            if all(term in name for term in normalized_terms):
                candidates.append(entry)
        return tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.catalog_type_code,
                    item.level is None,
                    item.level or Decimal("0"),
                    item.account_code,
                ),
            )
        )

    @classmethod
    def _normalize(cls, row: Mapping[str, Any]) -> SUGEFAccountCatalogEntry | None:
        account_code = cls._identifier(row.get("cuentaCatalogoSugef"))
        catalog_type_code = cls._identifier(row.get("codigoTipoCatalogo"))
        account_name = cls._text(row.get("nombreCuenta"))
        if not account_code or not catalog_type_code or not account_name:
            return None
        parent = cls._identifier(row.get("cuentaPadre")) or None
        return SUGEFAccountCatalogEntry(
            account_code=account_code,
            catalog_type_code=catalog_type_code,
            catalog_type_name=cls._text(row.get("nombreTipoCatalogo")),
            parent_account_code=parent,
            account_name=account_name,
            level=cls._decimal(row.get("nivelCuenta")),
            sign=cls._integer(row.get("signo")),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @classmethod
    def _integer(cls, value: Any) -> int | None:
        decimal = cls._decimal(value)
        if decimal is None or decimal != decimal.to_integral_value():
            return None
        return int(decimal)

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _identifier(cls, value: Any) -> str:
        if value is None or isinstance(value, bool):
            return ""
        if isinstance(value, str):
            text = value.strip()
            if text.endswith(".0") and text[:-2].replace("-", "").isdigit():
                return text[:-2]
            return text
        decimal = cls._decimal(value)
        if decimal is None or decimal != decimal.to_integral_value():
            return cls._text(value)
        # Si el API serializa el código como número, los ceros iniciales ya no
        # existen en el JSON. No se inventan ni se rellenan artificialmente.
        return str(int(decimal))

    @staticmethod
    def _normalize_text(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return " ".join(
            "".join(character for character in decomposed if not unicodedata.combining(character))
            .upper()
            .split()
        )
