from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from aip.product.configured.configuration.configured_source_config import ConfiguredSourceConfig
from aip.product.configured.configuration.institutional_paths import resolve_institutional_path
from aip.product.configured.protocols import SourceHealthProvider
from aip.product.demo.configuration.demo_config import DemoConfig


class ConfiguredPortfolioProvider:
    _EXCLUDED_DIRECTORIES = {
        "cuadre",
        "escritorio",
        "informe",
        "informes",
        "limites",
        "auditoria",
        "auditoria",
        "pruebas",
        "temporales",
        "respaldo",
        "respaldos",
    }
    _REJECT_TOKENS = ("prueba", "revision", "revisado", "copia", "respaldo", "canje", "historico")
    _DATE_PATTERN = re.compile(r"(?P<day>\d{1,2})[-.]?(?P<month>\d{1,2})[-.]?(?P<year>\d{4})")
    _SUPPORTED_EXTENSIONS = (".xls", ".xlsx")
    _DEFAULT_VECTOR_ALIASES = ("vector", "vector pipca", "vector pip")
    _MONTH_DIRECTORY_NAMES = {
        1: "enero",
        2: "febrero",
        3: "marzo",
        4: "abril",
        5: "mayo",
        6: "junio",
        7: "julio",
        8: "agosto",
        9: "setiembre",
        10: "octubre",
        11: "noviembre",
        12: "diciembre",
    }

    def __init__(self, config: DemoConfig, source_config: ConfiguredSourceConfig | None = None, health_provider: SourceHealthProvider | None = None) -> None:
        self._config = config
        self._source_config = source_config or ConfiguredSourceConfig()
        self._health_provider = health_provider

    def get_portfolio(self) -> dict[str, Any]:
        sql_enabled = self._source_config.sql_server.enabled
        folder_enabled = self._source_config.folder_watch.enabled
        source_status = self._health_provider.get_health() if self._health_provider is not None else {}
        portfolio_master = self._discover_portfolio_master()
        price_vector = self._discover_price_vector()
        data_quality_status = "HEALTHY" if portfolio_master["status"] == "HEALTHY" and price_vector["status"] in {"HEALTHY", "DISABLED"} else "DEGRADED"
        return {
            "portfolio_name": f"{self._config.environment_name.title()} Configured Portfolio",
            "valuation_date": self._config.data_cutoff_date.isoformat(),
            "market_value": 0.0 if not sql_enabled else 0.0,
            "book_value": 0.0 if not sql_enabled else 0.0,
            "weighted_yield": 0.0,
            "modified_duration": 0.0,
            "hqla_percent": 0.0,
            "mil_eligible_percent": 0.0,
            "currency_distribution": (),
            "relative_value_opportunity": "Unavailable",
            "positions": [],
            "source_status": source_status,
            "data_quality_status": data_quality_status,
            "portfolio_master": portfolio_master,
            "price_vector": price_vector,
            "configuration_message": "Portfolio sources are disabled or unavailable" if not (sql_enabled or folder_enabled) else "Configured sources are active",
        }

    def _discover_portfolio_master(self) -> dict[str, Any]:
        portfolio_root = self._source_config.folder_watch.portfolio_root
        if not portfolio_root:
            return self._source_result("UNAVAILABLE", "Portfolio root is not configured", expected_path=None, file_name=None, directory=None, valuation_date=None)

        investment_root = self._resolve_investment_root(portfolio_root)
        if investment_root is None:
            return self._source_result("UNAVAILABLE", "Institutional portfolio root could not be resolved", expected_path=portfolio_root, file_name=None, directory=None, valuation_date=None)

        cutoff_date = self._read_cutoff_date_override() or self._config.data_cutoff_date
        if not investment_root.exists():
            return self._source_result("UNAVAILABLE", "Institutional investment root does not exist", expected_path=str(investment_root), file_name=None, directory=None, valuation_date=None)

        canonical_base = investment_root / str(cutoff_date.year) / "maestro"
        canonical_directory = self._resolve_month_directory(canonical_base, cutoff_date.month)
        expected_directory = canonical_directory or canonical_base
        candidate_files = self._list_candidate_files(expected_directory)
        if canonical_directory is not None:
            exact_match = self._select_candidate_by_date(candidate_files, cutoff_date)
            if exact_match is not None:
                return self._source_result("HEALTHY", "Selected portfolio master file", expected_path=str(expected_directory), file_name=exact_match["file_name"], directory=exact_match["directory"], valuation_date=exact_match["valuation_date"].isoformat())

            if not self._allow_prior_source_date():
                return self._source_result("UNAVAILABLE", "No portfolio master file matched the requested cutoff date", expected_path=str(expected_directory), file_name=None, directory=str(expected_directory), valuation_date=None)

            prior_match = self._select_prior_candidate(candidate_files, cutoff_date, same_year_only=True)
            if prior_match is not None:
                age_days = (cutoff_date - prior_match["valuation_date"]).days
                return self._source_result(
                    "DEGRADED",
                    "Using a prior portfolio master file because the exact cutoff was unavailable",
                    expected_path=str(expected_directory),
                    file_name=prior_match["file_name"],
                    directory=prior_match["directory"],
                    valuation_date=prior_match["valuation_date"].isoformat(),
                    diagnostics={"selected_prior_date": prior_match["valuation_date"].isoformat(), "age_days": age_days},
                )

            for prior_month in range(cutoff_date.month - 1, 0, -1):
                prior_directory = self._resolve_month_directory(canonical_base, prior_month)
                if prior_directory is None:
                    continue
                prior_files = self._list_candidate_files(prior_directory)
                prior_match = self._select_prior_candidate(prior_files, cutoff_date, same_year_only=True)
                if prior_match is None:
                    continue
                age_days = (cutoff_date - prior_match["valuation_date"]).days
                return self._source_result(
                    "DEGRADED",
                    "Using a prior portfolio master file from an earlier month because the exact cutoff was unavailable",
                    expected_path=str(prior_directory),
                    file_name=prior_match["file_name"],
                    directory=prior_match["directory"],
                    valuation_date=prior_match["valuation_date"].isoformat(),
                    diagnostics={"selected_prior_date": prior_match["valuation_date"].isoformat(), "age_days": age_days},
                )

            return self._source_result("UNAVAILABLE", "No portfolio master file matched the requested cutoff date", expected_path=str(expected_directory), file_name=None, directory=str(expected_directory), valuation_date=None)

        if candidate_files:
            selected = self._select_latest_candidate(candidate_files)
            if selected is None:
                return self._source_result("DEGRADED", "No portfolio master file could be selected", expected_path=str(expected_directory), file_name=None, directory=str(expected_directory), valuation_date=None)
            return self._source_result("HEALTHY", "Selected portfolio master file", expected_path=str(expected_directory), file_name=selected["file_name"], directory=selected["directory"], valuation_date=selected["valuation_date"].isoformat())

        return self._discover_latest_master(investment_root)

    def _discover_price_vector(self) -> dict[str, Any]:
        vector_enabled = self._source_config.vector.enabled or self._source_config.folder_watch.enabled
        if not vector_enabled:
            return self._source_result("DISABLED", "Price vector discovery is disabled", expected_path=None, file_name=None, directory=None, valuation_date=None)

        cutoff_date = self._read_cutoff_date_override() or self._config.data_cutoff_date
        explicit_root = self._source_config.vector.path or self._source_config.vector.root or self._source_config.folder_watch.vector_path
        if explicit_root:
            vector_root = Path(resolve_institutional_path(explicit_root) or explicit_root)
            directory_candidates = [vector_root]
            directory_message = f"Using explicit vector root {vector_root}"
            directory_name = str(vector_root)
        else:
            portfolio_root = self._source_config.folder_watch.portfolio_root
            if not portfolio_root:
                return self._source_result("UNAVAILABLE", "Portfolio root is not configured for vector discovery", expected_path=None, file_name=None, directory=None, valuation_date=None)

            investment_root = self._resolve_investment_root(portfolio_root)
            if investment_root is None:
                return self._source_result("UNAVAILABLE", "Institutional portfolio root could not be resolved for vector discovery", expected_path=portfolio_root, file_name=None, directory=None, valuation_date=None)

            year_dir = investment_root / str(cutoff_date.year)
            alias_candidates = self._resolve_vector_directories(year_dir)
            if not alias_candidates:
                return self._source_result("UNAVAILABLE", "No supported vector directory was found for the current valuation year", expected_path=str(year_dir), file_name=None, directory=str(year_dir), valuation_date=None)
            if len(alias_candidates) > 1:
                return self._source_result("DEGRADED", "Multiple supported vector directories were found for the valuation year", expected_path=str(year_dir), file_name=None, directory=str(year_dir), valuation_date=None, directory_candidates=[str(path) for path in alias_candidates])
            vector_root = alias_candidates[0]
            directory_candidates = [vector_root]
            directory_message = f"Resolved vector directory {vector_root}"
            directory_name = vector_root.name

        if not vector_root.exists() or not vector_root.is_dir():
            return self._source_result("UNAVAILABLE", "Vector directory does not exist", expected_path=str(vector_root), file_name=None, directory=str(vector_root), valuation_date=None)

        month_directory = self._resolve_month_directory(vector_root, cutoff_date.month)
        target_directory: Path = month_directory or vector_root
        if month_directory is not None and not month_directory.exists():
            month_directory = None
            target_directory = vector_root

        candidate_files = self._list_candidate_files(target_directory)
        if not candidate_files:
            return self._source_result("DEGRADED", "No valid price-vector files were found in the resolved vector directory", expected_path=str(target_directory), file_name=None, directory=str(target_directory), valuation_date=None)

        if month_directory is not None:
            exact_match = self._select_candidate_by_date(candidate_files, cutoff_date)
            if exact_match is not None:
                return self._source_result("HEALTHY", directory_message, expected_path=str(target_directory), file_name=exact_match["file_name"], directory=exact_match["directory"], valuation_date=exact_match["valuation_date"].isoformat(), diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates]})

            if not self._allow_prior_source_date():
                return self._source_result("UNAVAILABLE", "No price-vector file matched the requested cutoff date", expected_path=str(target_directory), file_name=None, directory=str(target_directory), valuation_date=None, diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates]})

            prior_match = self._select_prior_candidate(candidate_files, cutoff_date, same_year_only=True)
            if prior_match is not None:
                age_days = (cutoff_date - prior_match["valuation_date"]).days
                return self._source_result(
                    "DEGRADED",
                    "Using a prior price-vector file because the exact cutoff was unavailable",
                    expected_path=str(target_directory),
                    file_name=prior_match["file_name"],
                    directory=prior_match["directory"],
                    valuation_date=prior_match["valuation_date"].isoformat(),
                    diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates], "selected_prior_date": prior_match["valuation_date"].isoformat(), "age_days": age_days},
                )

            for prior_month in range(cutoff_date.month - 1, 0, -1):
                prior_directory = self._resolve_month_directory(vector_root, prior_month)
                if prior_directory is None:
                    continue
                prior_files = self._list_candidate_files(prior_directory)
                prior_match = self._select_prior_candidate(prior_files, cutoff_date, same_year_only=True)
                if prior_match is None:
                    continue
                age_days = (cutoff_date - prior_match["valuation_date"]).days
                return self._source_result(
                    "DEGRADED",
                    "Using a prior price-vector file from an earlier month because the exact cutoff was unavailable",
                    expected_path=str(prior_directory),
                    file_name=prior_match["file_name"],
                    directory=prior_match["directory"],
                    valuation_date=prior_match["valuation_date"].isoformat(),
                    diagnostics={"candidate_count": len(prior_files), "directory_candidates": [str(path) for path in directory_candidates], "selected_prior_date": prior_match["valuation_date"].isoformat(), "age_days": age_days},
                )

            return self._source_result("UNAVAILABLE", "No price-vector file matched the requested cutoff date", expected_path=str(target_directory), file_name=None, directory=str(target_directory), valuation_date=None, diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates]})

        selected = self._select_latest_candidate(candidate_files)
        if selected is None:
            return self._source_result("DEGRADED", "No valid price-vector files could be selected", expected_path=str(target_directory), file_name=None, directory=str(target_directory), valuation_date=None, diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates]})
        return self._source_result("HEALTHY", directory_message, expected_path=str(target_directory), file_name=selected["file_name"], directory=selected["directory"], valuation_date=selected["valuation_date"].isoformat(), diagnostics={"candidate_count": len(candidate_files), "directory_candidates": [str(path) for path in directory_candidates]})

    def _discover_latest_master(self, investment_root: Path) -> dict[str, Any]:
        year_directories = [path for path in sorted(investment_root.iterdir(), key=lambda item: item.name) if path.is_dir() and path.name.isdigit()]
        for year_dir in reversed(year_directories):
            canonical_base = year_dir / "maestro"
            candidate_files = self._list_candidate_files(canonical_base)
            if candidate_files:
                selected = self._select_latest_candidate(candidate_files)
                if selected is not None:
                    return self._source_result("HEALTHY", "Selected portfolio master file", expected_path=str(canonical_base), file_name=selected["file_name"], directory=selected["directory"], valuation_date=selected["valuation_date"].isoformat())

            candidate_dirs = [self._resolve_month_directory(canonical_base, month) for month in range(12, 0, -1)]
            candidate_dirs = [directory for directory in candidate_dirs if directory is not None]
            for month_dir in candidate_dirs:
                candidate_files = self._list_candidate_files(month_dir)
                if not candidate_files:
                    continue
                selected = self._select_latest_candidate(candidate_files)
                if selected is None:
                    continue
                return self._source_result("HEALTHY", "Selected portfolio master file", expected_path=str(month_dir), file_name=selected["file_name"], directory=selected["directory"], valuation_date=selected["valuation_date"].isoformat())
        return self._source_result("UNAVAILABLE", "Canonical maestro directory was not found", expected_path=str(investment_root), file_name=None, directory=None, valuation_date=None)

    def _select_candidate_by_date(self, candidate_files: list[dict[str, Any]], cutoff_date: date) -> dict[str, Any] | None:
        matching_files = [candidate for candidate in candidate_files if candidate["valuation_date"] == cutoff_date]
        if not matching_files:
            return None
        return self._select_best_candidate(matching_files)

    def _select_prior_candidate(self, candidate_files: list[dict[str, Any]], cutoff_date: date, *, same_year_only: bool = False) -> dict[str, Any] | None:
        matching_files = [candidate for candidate in candidate_files if candidate["valuation_date"] < cutoff_date]
        if same_year_only:
            matching_files = [candidate for candidate in matching_files if candidate["valuation_date"].year == cutoff_date.year]
        if not matching_files:
            return None
        matching_files.sort(key=lambda candidate: candidate["valuation_date"])
        return matching_files[-1]

    def _select_latest_candidate(self, candidate_files: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidate_files:
            return None
        best_candidate = self._select_best_candidate(candidate_files)
        if best_candidate is not None:
            return best_candidate
        latest = max(candidate_files, key=lambda candidate: candidate["valuation_date"])
        return latest

    def _select_best_candidate(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None
        ranked = []
        for candidate in candidates:
            score = 0
            normalized_name = candidate["normalized_name"]
            stem = normalized_name.rsplit(".", 1)[0]
            expected_stem = candidate["valuation_date"].strftime("%d-%m-%Y")
            if stem == expected_stem:
                score += 4
            elif stem.startswith(expected_stem):
                score -= 1
            if any(token in normalized_name for token in ("-2", "-3")):
                score -= 3
            ranked.append((score, candidate))
        ranked.sort(key=lambda item: (-item[0], item[1]["file_name"]))
        top_score = ranked[0][0]
        top_candidates = [candidate for score, candidate in ranked if score == top_score]
        if len(top_candidates) > 1:
            return None
        return top_candidates[0]

    def _list_candidate_files(self, directory: Path) -> list[dict[str, Any]]:
        if not directory.exists() or not directory.is_dir():
            return []
        candidates: list[dict[str, Any]] = []
        for file_path in sorted(directory.iterdir(), key=lambda item: item.name):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._SUPPORTED_EXTENSIONS:
                continue
            normalized_name = self._normalize_name(file_path.name)
            parsed_date = self._parse_date_from_name(normalized_name)
            if parsed_date is None:
                continue
            if self._is_rejected_name(normalized_name):
                continue
            candidates.append({
                "file_name": file_path.name,
                "normalized_name": normalized_name,
                "valuation_date": parsed_date,
                "directory": str(directory),
                "path": str(file_path),
            })
        return candidates

    def _parse_date_from_name(self, name: str) -> date | None:
        match = self._DATE_PATTERN.search(name)
        if not match:
            return None
        try:
            return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
        except ValueError:
            return None

    def _normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", name).strip().lower()

    def _is_rejected_name(self, name: str) -> bool:
        lower_name = name.lower()
        return any(token in lower_name for token in self._REJECT_TOKENS)

    def _resolve_investment_root(self, portfolio_root: str | None) -> Path | None:
        if not portfolio_root:
            return None
        normalized_root = resolve_institutional_path(portfolio_root)
        if not normalized_root:
            return None
        root_path = Path(normalized_root)
        if root_path.name.lower() == "inversiones":
            return root_path
        if root_path.exists() and root_path.is_dir() and (root_path / "Inversiones").exists():
            return root_path / "Inversiones"
        return root_path / "Inversiones"

    def _resolve_month_directory(self, parent_dir: Path, month: int) -> Path | None:
        if not parent_dir.exists() or not parent_dir.is_dir():
            return None
        canonical_name = self._MONTH_DIRECTORY_NAMES[month]
        for directory in sorted(parent_dir.iterdir(), key=lambda item: item.name):
            if not directory.is_dir():
                continue
            if self._normalize_month_name(directory.name) == canonical_name:
                return directory
        return None

    def _normalize_month_name(self, value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value))
        ascii_text = text.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"\s+", " ", ascii_text).strip().lower()
        if normalized in {"septiembre", "setiembre"}:
            return "setiembre"
        return normalized

    def _resolve_vector_directories(self, year_dir: Path) -> list[Path]:
        if not year_dir.exists() or not year_dir.is_dir():
            return []
        alias_candidates: list[Path] = []
        aliases = self._vector_aliases()
        for alias in aliases:
            alias_dir = year_dir / alias
            if alias_dir.exists() and alias_dir.is_dir():
                alias_candidates.append(alias_dir)
        return alias_candidates

    def _vector_aliases(self) -> list[str]:
        config_aliases = self._source_config.vector.directory_aliases
        if config_aliases:
            return [self._normalize_alias(item) for item in config_aliases if self._normalize_alias(item)]
        metadata_aliases = self._source_config.metadata.get("vector_directory_aliases") if self._source_config.metadata else None
        if isinstance(metadata_aliases, str):
            return [self._normalize_alias(item) for item in metadata_aliases.split(",") if self._normalize_alias(item)]
        if isinstance(metadata_aliases, (list, tuple)):
            return [self._normalize_alias(item) for item in metadata_aliases if self._normalize_alias(item)]
        return [self._normalize_alias(item) for item in self._DEFAULT_VECTOR_ALIASES if self._normalize_alias(item)]

    def _normalize_alias(self, value: Any) -> str:
        text = str(value).strip()
        if not text:
            return ""
        return re.sub(r"\s+", " ", text)

    def _allow_prior_source_date(self) -> bool:
        value = self._source_config.metadata.get("allow_prior_source_date") if self._source_config.metadata else None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return False

    def _read_cutoff_date_override(self) -> date | None:
        override_value = self._source_config.metadata.get("data_cutoff_date") if self._source_config.metadata else None
        if isinstance(override_value, date):
            return override_value
        if isinstance(override_value, str):
            try:
                return date.fromisoformat(override_value)
            except ValueError:
                return None
        return None

    def _source_result(self, status: str, message: str, *, expected_path: str | None, file_name: str | None, directory: str | None, valuation_date: str | None, diagnostics: dict[str, Any] | None = None, directory_candidates: list[str] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": status,
            "message": message,
            "expected_path": expected_path,
            "file_name": file_name,
            "directory": directory,
            "valuation_date": valuation_date,
            "diagnostics": diagnostics or {},
        }
        if directory_candidates is not None:
            result["directory_candidates"] = directory_candidates
        return result
