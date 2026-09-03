from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.configuration.configured_source_config import (
    ConfiguredSourceConfig,
)
from aip.product.configured.context.valuation_date_context import ValuationDateContext
from aip.product.configured.protocols import (
    PortfolioDataProvider,
    SourceHealthProvider,
)
from aip.product.configured.readers.institutional_icl_reader import (
    InstitutionalICLReader,
)
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredLiquidityProvider:
    """Configured institutional liquidity provider.

    Combines:
    - institutional ICL data;
    - enriched portfolio positions;
    - HQLA attributes already calculated upstream;
    - MIL attributes already calculated upstream;
    - contractual investment maturities.

    No financial eligibility rules are recalculated here.
    """

    def __init__(
        self,
        config: DemoConfig,
        source_config: ConfiguredSourceConfig | None = None,
        health_provider: SourceHealthProvider | None = None,
        portfolio_provider: PortfolioDataProvider | None = None,
        valuation_date_context: ValuationDateContext | None = None,
    ) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider
        self._portfolio_provider = portfolio_provider
        self._valuation_date_context = valuation_date_context

    def get_liquidity(
        self,
    ) -> dict[str, Any]:
        folder_enabled = self._source_config.folder_watch.enabled

        sql_enabled = self._source_config.sql_server.enabled

        source_status = (
            self._health_provider.get_health() if self._health_provider is not None else {}
        )

        result: dict[str, Any] = {
            "liquidity_date": (self._current_cutoff_date().isoformat()),
            # -----------------------------------------------------
            # ICL / Flujo
            # -----------------------------------------------------
            "cash_position": 0.0,
            "net_cash_flow": 0.0,
            "liquidity_gap": 0.0,
            "icl_total": 0.0,
            "icl_mn": 0.0,
            "icl_me": 0.0,
            "liquid_asset_fund_total": 0.0,
            "liquid_asset_fund_mn": 0.0,
            "liquid_asset_fund_me": 0.0,
            "total_outflows_30d": 0.0,
            "total_inflows_30d": 0.0,
            "net_cash_outflow_30d": 0.0,
            # -----------------------------------------------------
            # HQLA
            # -----------------------------------------------------
            "hqla_capacity": 0.0,
            "hqla_market_value_crc": 0.0,
            "hqla_eligible_count": 0,
            "hqla_restricted_count": 0,
            "hqla_not_eligible_count": 0,
            "hqla_eligible_market_value_crc": 0.0,
            "hqla_restricted_market_value_crc": 0.0,
            "hqla_not_eligible_market_value_crc": 0.0,
            # -----------------------------------------------------
            # MIL
            # -----------------------------------------------------
            "mil_eligible_capacity": 0.0,
            "mil_market_value_crc": 0.0,
            "mil_eligible_count": 0,
            "mil_restricted_count": 0,
            "mil_not_eligible_count": 0,
            "mil_eligible_market_value_crc": 0.0,
            "mil_restricted_market_value_crc": 0.0,
            "mil_not_eligible_market_value_crc": 0.0,
            # -----------------------------------------------------
            # Vencimientos
            # -----------------------------------------------------
            "maturity_30d_crc": 0.0,
            "maturity_90d_crc": 0.0,
            "maturity_180d_crc": 0.0,
            "maturity_270d_crc": 0.0,
            "maturity_rows": [],
            # -----------------------------------------------------
            # Estado / análisis todavía no implementado
            # -----------------------------------------------------
            "stress_result": "No configurado",
            "policy_status": "No evaluado",
            "cashflows": [],
            "gaps": [],
            "hqla_rows": [],
            "mil_rows": [],
            "stress_rows": [],
            "source_status": source_status,
            "data_quality_status": ("HEALTHY" if sql_enabled or folder_enabled else "DEGRADED"),
            "configuration_message": (
                "Liquidity sources are disabled or unavailable"
                if not (sql_enabled or folder_enabled)
                else "Configured liquidity sources are active"
            ),
        }

        # =========================================================
        # PORTAFOLIO ENRIQUECIDO
        # =========================================================

        portfolio = self._load_portfolio()

        positions = (
            portfolio.get(
                "positions",
                [],
            )
            if portfolio
            else []
        )

        if positions:
            self._populate_portfolio_liquidity(
                result=result,
                positions=positions,
                valuation_date=self._resolve_valuation_date(portfolio),
            )

        # =========================================================
        # ICL
        # =========================================================

        icl_file = self._discover_icl_file(self._current_cutoff_date())

        if icl_file is None:
            if positions:
                result["configuration_message"] = (
                    "Portfolio liquidity loaded; " "ICL file unavailable for configured cutoff date"
                )
            else:
                result["configuration_message"] = "ICL file unavailable for configured cutoff date"

            return result

        icl = InstitutionalICLReader().read(icl_file)

        result.update(
            {
                "liquidity_date": (icl.valuation_date.isoformat()),
                "cash_position": float(icl.liquid_asset_fund_total),
                "net_cash_flow": float(icl.total_inflows_30d_total - icl.total_outflows_30d_total),
                "liquidity_gap": float(icl.total_inflows_30d_total - icl.total_outflows_30d_total),
                "icl_total": float(icl.icl_total),
                "icl_mn": float(icl.icl_mn),
                "icl_me": float(icl.icl_me),
                "liquid_asset_fund_total": float(icl.liquid_asset_fund_total),
                "liquid_asset_fund_mn": float(icl.liquid_asset_fund_mn),
                "liquid_asset_fund_me": float(icl.liquid_asset_fund_me),
                "total_outflows_30d": float(icl.total_outflows_30d_total),
                "total_inflows_30d": float(icl.total_inflows_30d_total),
                "net_cash_outflow_30d": float(icl.net_cash_outflow_30d_total),
                "icl_source_file": (icl.source_file),
                "icl_source_date": (icl.valuation_date.isoformat()),
                "stress_result": "No configurado",
                "policy_status": "No evaluado",
                "icl_diagnostics": (icl.diagnostics),
                "icl_warnings": (
                    list(icl.warnings)
                    + (
                        [
                            "ICL prior-date fallback used: "
                            f"source={icl.valuation_date.isoformat()} "
                            f"cutoff={self._current_cutoff_date().isoformat()}"
                        ]
                        if icl.valuation_date < self._current_cutoff_date()
                        else []
                    )
                ),
                "configuration_message": (
                    "Institutional ICL and enriched portfolio " "liquidity sources loaded"
                    if positions
                    else "Institutional ICL source loaded"
                ),
            }
        )

        return result

    # =============================================================
    # PORTAFOLIO
    # =============================================================

    def _load_portfolio(
        self,
    ) -> dict[str, Any]:
        if self._portfolio_provider is None:
            return {}

        try:
            return self._portfolio_provider.get_portfolio() or {}
        except Exception:
            return {}

    def _current_cutoff_date(self) -> date:
        if self._valuation_date_context is not None:
            return self._valuation_date_context.value
        return self._config.data_cutoff_date

    def _resolve_valuation_date(
        self,
        portfolio: dict[str, Any],
    ) -> date:
        raw = portfolio.get("valuation_date") or self._config.data_cutoff_date

        if isinstance(
            raw,
            date,
        ):
            return raw

        if isinstance(
            raw,
            str,
        ):
            try:
                return date.fromisoformat(raw)
            except ValueError:
                pass

        return self._current_cutoff_date()

    def _populate_portfolio_liquidity(
        self,
        *,
        result: dict[str, Any],
        positions: list[dict[str, Any]],
        valuation_date: date,
    ) -> None:
        hqla_rows: list[dict[str, Any]] = []

        mil_rows: list[dict[str, Any]] = []

        maturity_rows: list[dict[str, Any]] = []

        hqla_capacity = 0.0
        hqla_market_value = 0.0

        hqla_eligible_count = 0
        hqla_restricted_count = 0
        hqla_not_eligible_count = 0

        hqla_eligible_market_value = 0.0
        hqla_restricted_market_value = 0.0
        hqla_not_eligible_market_value = 0.0

        mil_capacity = 0.0
        mil_market_value = 0.0

        mil_eligible_count = 0
        mil_restricted_count = 0
        mil_not_eligible_count = 0

        mil_eligible_market_value = 0.0
        mil_restricted_market_value = 0.0
        mil_not_eligible_market_value = 0.0

        maturity_30d = 0.0
        maturity_90d = 0.0
        maturity_180d = 0.0
        maturity_270d = 0.0

        for position in positions:
            market_value_crc = self._float_value(position.get("market_value_crc"))

            # =====================================================
            # HQLA
            # =====================================================

            hqla_status = (
                str(
                    position.get(
                        "hqla_status",
                        "NOT_ELIGIBLE",
                    )
                )
                .strip()
                .upper()
            )

            hqla_value_crc = self._float_value(position.get("hqla_value_crc"))

            hqla_factor = self._float_value(position.get("hqla_factor"))

            if hqla_status in {
                "HQLA_100",
                "HQLA_90",
            }:
                hqla_capacity += hqla_value_crc

                hqla_market_value += market_value_crc

                hqla_eligible_count += 1

                hqla_eligible_market_value += market_value_crc

            elif hqla_status == "RESTRICTED":
                hqla_restricted_count += 1

                hqla_restricted_market_value += market_value_crc

            else:
                hqla_not_eligible_count += 1

                hqla_not_eligible_market_value += market_value_crc

            hqla_rows.append(
                {
                    "section": "HQLA",
                    "label": str(position.get("series") or position.get("instrument") or ""),
                    "issuer": str(
                        position.get(
                            "issuer",
                            "",
                        )
                    ),
                    "currency": str(
                        position.get(
                            "currency",
                            "",
                        )
                    ),
                    "classification": str(
                        position.get(
                            "classification",
                            "",
                        )
                    ),
                    "market_value_crc": (market_value_crc),
                    "value": (hqla_value_crc),
                    "factor": (hqla_factor),
                    "status": (hqla_status),
                    "policy_reference": str(
                        position.get(
                            "hqla_source",
                            "",
                        )
                    ),
                    "maturity_date": (self._date_text(position.get("maturity_date"))),
                }
            )

            # =====================================================
            # MIL
            # =====================================================

            mil_status = (
                str(
                    position.get(
                        "mil_status",
                        "NOT_ELIGIBLE",
                    )
                )
                .strip()
                .upper()
            )

            mil_value_crc = self._float_value(position.get("mil_value_crc"))

            mil_factor = self._float_value(position.get("mil_factor"))

            if mil_status == "MIL_ELIGIBLE":
                mil_capacity += mil_value_crc

                mil_market_value += market_value_crc

                mil_eligible_count += 1

                mil_eligible_market_value += market_value_crc

            elif mil_status == "RESTRICTED":
                mil_restricted_count += 1

                mil_restricted_market_value += market_value_crc

            else:
                mil_not_eligible_count += 1

                mil_not_eligible_market_value += market_value_crc

            mil_rows.append(
                {
                    "section": "MIL",
                    "label": str(position.get("series") or position.get("instrument") or ""),
                    "issuer": str(
                        position.get(
                            "issuer",
                            "",
                        )
                    ),
                    "currency": str(
                        position.get(
                            "currency",
                            "",
                        )
                    ),
                    "classification": str(
                        position.get(
                            "classification",
                            "",
                        )
                    ),
                    "market_value_crc": (market_value_crc),
                    "value": (mil_value_crc),
                    "factor": (mil_factor),
                    "status": (mil_status),
                    "policy_reference": str(
                        position.get(
                            "mil_source",
                            "",
                        )
                    ),
                    "maturity_date": (self._date_text(position.get("maturity_date"))),
                }
            )

            # =====================================================
            # VENCIMIENTOS
            # =====================================================

            maturity = self._as_date(position.get("maturity_date"))

            if maturity is None:
                continue

            days = (maturity - valuation_date).days

            if days < 0:
                continue

            bucket = self._maturity_bucket(days)

            maturity_rows.append(
                {
                    "section": "MATURITY",
                    "label": str(position.get("series") or position.get("instrument") or ""),
                    "issuer": str(
                        position.get(
                            "issuer",
                            "",
                        )
                    ),
                    "currency": str(
                        position.get(
                            "currency",
                            "",
                        )
                    ),
                    "classification": str(
                        position.get(
                            "classification",
                            "",
                        )
                    ),
                    "maturity_date": (maturity.isoformat()),
                    "days_to_maturity": (days),
                    "bucket": bucket,
                    "value": market_value_crc,
                    "market_value_crc": (market_value_crc),
                    "status": "AVAILABLE",
                }
            )

            if days <= 30:
                maturity_30d += market_value_crc

            if days <= 90:
                maturity_90d += market_value_crc

            if days <= 180:
                maturity_180d += market_value_crc

            if days <= 270:
                maturity_270d += market_value_crc

        # =========================================================
        # ORDEN
        # =========================================================

        hqla_rows.sort(
            key=lambda row: (
                self._status_order(
                    str(
                        row.get(
                            "status",
                            "",
                        )
                    )
                ),
                -self._float_value(row.get("value")),
            )
        )

        mil_rows.sort(
            key=lambda row: (
                self._status_order(
                    str(
                        row.get(
                            "status",
                            "",
                        )
                    )
                ),
                -self._float_value(row.get("value")),
            )
        )

        maturity_rows.sort(
            key=lambda row: (
                int(
                    row.get(
                        "days_to_maturity",
                        999999,
                    )
                ),
                str(
                    row.get(
                        "label",
                        "",
                    )
                ),
            )
        )

        # =========================================================
        # PAYLOAD
        # =========================================================

        result.update(
            {
                "hqla_capacity": (hqla_capacity),
                "hqla_market_value_crc": (hqla_market_value),
                "hqla_eligible_count": (hqla_eligible_count),
                "hqla_restricted_count": (hqla_restricted_count),
                "hqla_not_eligible_count": (hqla_not_eligible_count),
                "hqla_eligible_market_value_crc": (hqla_eligible_market_value),
                "hqla_restricted_market_value_crc": (hqla_restricted_market_value),
                "hqla_not_eligible_market_value_crc": (hqla_not_eligible_market_value),
                "mil_eligible_capacity": (mil_capacity),
                "mil_market_value_crc": (mil_market_value),
                "mil_eligible_count": (mil_eligible_count),
                "mil_restricted_count": (mil_restricted_count),
                "mil_not_eligible_count": (mil_not_eligible_count),
                "mil_eligible_market_value_crc": (mil_eligible_market_value),
                "mil_restricted_market_value_crc": (mil_restricted_market_value),
                "mil_not_eligible_market_value_crc": (mil_not_eligible_market_value),
                "maturity_30d_crc": (maturity_30d),
                "maturity_90d_crc": (maturity_90d),
                "maturity_180d_crc": (maturity_180d),
                "maturity_270d_crc": (maturity_270d),
                "hqla_rows": (hqla_rows),
                "mil_rows": (mil_rows),
                "maturity_rows": (maturity_rows),
            }
        )

    # =============================================================
    # ICL DISCOVERY
    # =============================================================

    def _discover_icl_file(
        self,
        cutoff_date: date,
    ) -> Path | None:
        root_value = self._source_config.folder_watch.icl_root
        if not root_value:
            return None

        root = Path(root_value)
        if not root.exists():
            return None

        search_root = self._resolve_icl_search_root(root)
        candidates: list[tuple[date, Path]] = []
        for candidate in search_root.rglob("*.xls*"):
            if not candidate.is_file():
                continue
            document_date = self._icl_document_date(candidate)
            if document_date is None:
                continue
            candidates.append((document_date, candidate))

        if not candidates:
            return None

        exact = [path for document_date, path in candidates if document_date == cutoff_date]
        if exact:
            return sorted(exact, key=lambda item: str(item).casefold())[0]

        allow_prior = self._source_config.metadata.get("allow_prior_source_date", False)
        if isinstance(allow_prior, str):
            allow_prior = allow_prior.strip().lower() in {"1", "true", "yes", "on"}
        if not bool(allow_prior):
            return None

        raw_max_age = self._source_config.metadata.get("icl_max_prior_days", 7)
        try:
            max_age_days = max(0, int(raw_max_age))
        except (TypeError, ValueError):
            max_age_days = 7

        prior = [
            (document_date, path)
            for document_date, path in candidates
            if document_date < cutoff_date and (cutoff_date - document_date).days <= max_age_days
        ]
        if not prior:
            return None

        latest_date = max(document_date for document_date, _ in prior)
        latest_paths = [path for document_date, path in prior if document_date == latest_date]
        return sorted(latest_paths, key=lambda item: str(item).casefold())[0]

    @staticmethod
    def _resolve_icl_search_root(root: Path) -> Path:
        """Resolve the narrowest institutional ICL report directory available."""
        candidates = (
            root / "ICL" / "Reportes ICL",
            root / "Reportes ICL",
            root,
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return root

    @staticmethod
    def _icl_document_date(candidate: Path) -> date | None:
        """Parse institutional ICL filenames without relying on separators."""
        normalized = candidate.stem.upper().replace("_", " ").replace("-", " ").replace(".", " ")
        normalized = " ".join(normalized.split())
        tokens = normalized.split()
        month_numbers = {
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
        for index, token in enumerate(tokens):
            month = month_numbers.get(token)
            if month is None or index == 0 or index + 1 >= len(tokens):
                continue
            try:
                day = int(tokens[index - 1])
                year = int(tokens[index + 1])
                return date(year, month, day)
            except (TypeError, ValueError):
                continue
        return None

    # =============================================================
    # HELPERS
    # =============================================================

    @staticmethod
    def _float_value(
        value: object,
    ) -> float:
        if value is None:
            return 0.0

        try:
            return float(str(value))
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _as_date(
        value: object,
    ) -> date | None:
        if isinstance(
            value,
            date,
        ):
            return value

        if (
            isinstance(
                value,
                str,
            )
            and value
        ):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None

        return None

    @classmethod
    def _date_text(
        cls,
        value: object,
    ) -> str:
        parsed = cls._as_date(value)

        return parsed.isoformat() if parsed is not None else ""

    @staticmethod
    def _maturity_bucket(
        days: int,
    ) -> str:
        if days <= 30:
            return "0-30D"

        if days <= 90:
            return "31-90D"

        if days <= 180:
            return "91-180D"

        if days <= 270:
            return "181-270D"

        return ">270D"

    @staticmethod
    def _status_order(
        status: str,
    ) -> int:
        normalized = status.strip().upper()

        if normalized in {
            "HQLA_100",
            "HQLA_90",
            "MIL_ELIGIBLE",
        }:
            return 0

        if normalized == "RESTRICTED":
            return 1

        return 2
