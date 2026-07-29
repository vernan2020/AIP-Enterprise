from __future__ import annotations

from typing import Any

from aip.integration.audit.execution_result import ExecutionStatus
from aip.integration.sqlserver.connector.connection_pool import ConnectionPool
from aip.integration.sqlserver.contracts.sql_request import SQLRequest
from aip.integration.sqlserver.contracts.sql_result import SQLExecutionResult
from aip.integration.sqlserver.validation.sql_validator import SQLValidator


def _token_is_cancelled(token: Any) -> bool:
    if token is None:
        return False
    if token is True:
        return True
    if isinstance(token, str):
        return token.strip().lower() in {"cancelled", "canceled", "stop", "abort"}
    if callable(token):
        try:
            return bool(token())
        except TypeError:
            return False
    if hasattr(token, "is_cancelled"):
        return bool(getattr(token, "is_cancelled"))
    return False


class SQLSynchronizer:
    """Executes parameterized SQL requests with optional streaming semantics."""

    def __init__(
        self,
        pool: ConnectionPool,
        validator: SQLValidator | None = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.0,
    ) -> None:
        self.pool = pool
        self.validator = validator or SQLValidator()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def synchronize(self, request: SQLRequest) -> SQLExecutionResult:
        validation_result = self.validator.validate(request)
        if not validation_result.ok:
            return SQLExecutionResult(
                query_name=request.query_name,
                status=ExecutionStatus.FAILED,
                errors=[issue.message for issue in validation_result.issues],
                row_count=0,
                streaming=request.stream,
            )

        if _token_is_cancelled(request.cancellation_token):
            return SQLExecutionResult(
                query_name=request.query_name,
                status=ExecutionStatus.CANCELLED,
                errors=["request was cancelled"],
                row_count=0,
                streaming=request.stream,
                checkpoint=request.checkpoint,
            )

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                connection = self.pool.acquire()
                try:
                    cursor = connection.cursor()
                    cursor.execute(request.query_text, request.parameters)
                    rows = cursor.fetchall()
                    return SQLExecutionResult(
                        query_name=request.query_name,
                        row_count=len(rows),
                        rows=rows,
                        streaming=request.stream,
                        checkpoint=request.checkpoint,
                        status=ExecutionStatus.COMPLETED,
                        retries=attempt,
                    )
                finally:
                    self.pool.release(connection)
            except Exception as exc:  # pragma: no cover - exercised in tests
                last_error = str(exc)
                if attempt >= self.max_retries:
                    break

        return SQLExecutionResult(
            query_name=request.query_name,
            status=ExecutionStatus.FAILED,
            errors=[last_error or "execution failed"],
            row_count=0,
            streaming=request.stream,
            checkpoint=request.checkpoint,
            retries=self.max_retries,
        )
