from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aip.integration.audit.execution_result import ExecutionStatus


@dataclass(slots=True)
class SQLExecutionResult:
    """Structured execution result for SQL synchronization."""

    query_name: str
    row_count: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)
    streaming: bool = False
    checkpoint: str | None = None
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_id: str | None = None
    correlation_id: str | None = None
    connector: str = "sqlserver"
    duration_seconds: float = 0.0
    retries: int = 0
