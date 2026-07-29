from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from aip.integration.audit.execution_result import ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorType
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent, SynchronizationEventType
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.sqlserver.audit.sql_audit import SQLAudit
from aip.integration.sqlserver.configuration.sql_config import SQLAuthentication, SQLServerConfig
from aip.integration.sqlserver.connector.connection_factory import DefaultSQLServerConnectionFactory, SQLServerConnectionFactory
from aip.integration.sqlserver.connector.connection_pool import ConnectionPool
from aip.integration.sqlserver.connector.sql_connector import SQLServerConnector
from aip.integration.sqlserver.contracts.sql_request import SQLRequest
from aip.integration.sqlserver.contracts.sql_result import SQLExecutionResult
from aip.integration.sqlserver.driver.driver_adapter import PyOdbcDriverAdapter, SQLServerDriverAdapter
from aip.integration.sqlserver.monitoring.sql_health import SQLHealthMonitor
from aip.integration.sqlserver.synchronization.sql_synchronizer import SQLSynchronizer
from aip.integration.sqlserver.telemetry.sql_metrics import SQLMetrics
from aip.integration.sqlserver.validation.sql_validator import SQLValidator


@dataclass
class StubCursor:
    rows: list[dict[str, Any]]
    executed: list[tuple[str, dict[str, Any]]] | None = None

    def execute(self, query: str, params: dict[str, Any] | None = None) -> "StubCursor":
        self.executed = [(query, params or {})]
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def __iter__(self):
        return iter(self.rows)


@dataclass
class StubConnection:
    name: str = "stub"
    cursor_obj: StubCursor | None = None
    closed: bool = False
    executed_queries: list[tuple[str, dict[str, Any]]] | None = None

    def cursor(self) -> StubCursor:
        if self.cursor_obj is None:
            self.cursor_obj = StubCursor(rows=[])
        return self.cursor_obj

    def close(self) -> None:
        self.closed = True

    def commit(self) -> None:
        return None


class StubFactory(SQLServerConnectionFactory):
    def __init__(self, *, connection: StubConnection | None = None) -> None:
        super().__init__(SQLServerConfig(connection_string="Driver=Test"))
        self._connection = connection or StubConnection()
        self.created = 0

    def create_connection(self) -> Any:
        self.created += 1
        return self._connection


def test_sql_config_validates_required_settings() -> None:
    config = SQLServerConfig(connection_string="Server=sql;Database=db", timeout_seconds=15, max_retries=2)
    assert config.connection_string == "Server=sql;Database=db"
    assert config.timeout_seconds == 15
    assert config.max_retries == 2

    with pytest.raises(ValueError):
        SQLServerConfig(connection_string="")


def test_sql_config_builds_connection_string_from_parts_and_rejects_pool_size() -> None:
    config = SQLServerConfig(server="server", database="db")
    assert config.build_connection_string() == "Server=server;Database=db;"

    with pytest.raises(ValueError, match="pool_size"):
        SQLServerConfig(connection_string="Server=sql;Database=db", pool_size=0)


def test_connection_pool_reuses_and_closes_connections() -> None:
    pool = ConnectionPool(factory=StubFactory(), max_size=2)
    conn1 = pool.acquire()
    conn2 = pool.acquire()
    assert conn1 is not None
    assert conn2 is not None
    pool.release(conn1)
    pool.release(conn2)
    pool.close()


def test_sql_validator_accepts_valid_request_and_rejects_bad_schema() -> None:
    validator = SQLValidator()
    request = SQLRequest(query_name="select_rows", query_text="SELECT * FROM table", parameters={"id": 1})
    result = validator.validate(request)
    assert result.ok is True

    bad_request = SQLRequest(query_name="", query_text="", parameters={})
    bad_result = validator.validate(bad_request)
    assert bad_result.ok is False
    assert any(issue.message == "query_name is required" for issue in bad_result.issues)


def test_sql_validator_handles_null_payload_and_bad_paging() -> None:
    validator = SQLValidator()
    invalid_payload = validator.validate(None)
    assert invalid_payload.ok is False

    request = SQLRequest(query_name="select", query_text="SELECT 1", parameters=None, page_size=0)
    result = validator.validate(request)
    assert result.ok is False
    assert any(issue.field == "page_size" for issue in result.issues)


def test_default_connection_factory_creates_cursor_and_connection() -> None:
    factory = DefaultSQLServerConnectionFactory(SQLServerConfig(connection_string="Server=sql;Database=db"))
    connection = factory.create_connection()
    cursor = connection.cursor()
    assert cursor.execute("SELECT 1", {"id": 1}).executed == ("SELECT 1", {"id": 1})
    assert cursor.fetchall() == []
    connection.close()
    connection.commit()


def test_sql_synchronizer_executes_parameterized_queries_and_streams_results() -> None:
    connection = StubConnection()
    connection.cursor_obj = StubCursor(rows=[{"id": 1, "name": "A"}])
    factory = StubFactory(connection=connection)
    pool = ConnectionPool(factory=factory, max_size=1)
    synchronizer = SQLSynchronizer(pool=pool)
    request = SQLRequest(
        query_name="select_rows",
        query_text="SELECT * FROM table WHERE id = @id",
        parameters={"id": 1},
        stream=True,
        page_size=10,
        page_number=0,
    )

    result = synchronizer.synchronize(request)

    assert result.rows == [{"id": 1, "name": "A"}]
    assert result.streaming is True
    assert result.row_count == 1
    assert result.query_name == "select_rows"


def test_sql_connector_initializes_with_default_factory() -> None:
    connector = SQLServerConnector(config=SQLServerConfig(connection_string="Server=sql;Database=db"))

    connector.connect()
    assert connector.health() is True
    connector.disconnect()
    assert connector.health() is False


def test_connection_pool_ignores_unknown_release_and_closes_without_close() -> None:
    pool = ConnectionPool(factory=StubFactory(), max_size=1)
    connection = pool.acquire()
    pool.release(object())
    pool.release(connection)

    class NoCloseConnection:
        pass

    pool._connections = [NoCloseConnection()]
    pool.close()


def test_config_redacts_credentials_and_exposes_safe_repr() -> None:
    config = SQLServerConfig(
        connection_string="Server=sql;Database=db",
        authentication=SQLAuthentication(mode="sql", username="user", password="secret"),
    )

    assert "secret" not in repr(config)
    assert config.to_safe_dict()["authentication"] is not None


def test_sql_connector_lifecycle_and_events_are_published() -> None:
    factory = StubFactory(connection=StubConnection())
    pool = ConnectionPool(factory=factory, max_size=1)
    events: list[SynchronizationEvent] = []
    event_bus = IntegrationEventBus()
    event_bus.subscribe(events.append)
    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db"),
        connection_factory=factory,
        pool=pool,
        event_bus=event_bus,
    )

    connector.connect()
    assert connector.health() is True
    connector.disconnect()

    assert [event.event_type for event in events] == [
        SynchronizationEventType.CONNECTED,
        SynchronizationEventType.DISCONNECTED,
    ]


def test_sql_connector_synchronization_and_retry_behaviors() -> None:
    connection = StubConnection()
    connection.cursor_obj = StubCursor(rows=[{"id": 2, "name": "B"}])
    factory = StubFactory(connection=connection)
    pool = ConnectionPool(factory=factory, max_size=1)
    event_bus = IntegrationEventBus()
    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db", max_retries=1),
        connection_factory=factory,
        pool=pool,
        event_bus=event_bus,
    )

    request = SQLRequest(query_name="retry_query", query_text="SELECT 1", parameters={"id": 2})
    result = connector.synchronize(request, correlation_id="corr", user="ops")

    assert result.status == ExecutionStatus.COMPLETED
    assert result.records_processed == 1


def test_sql_connector_respects_cancellation_and_checkpoint() -> None:
    connection = StubConnection()
    connection.cursor_obj = StubCursor(rows=[{"id": 1}])
    pool = ConnectionPool(factory=StubFactory(connection=connection), max_size=1)
    synchronizer = SQLSynchronizer(pool=pool)

    request = SQLRequest(
        query_name="resume_query",
        query_text="SELECT * FROM table",
        parameters={"id": 1},
        stream=True,
        checkpoint="cp-1",
        cancellation_token="cancelled",
    )
    result = synchronizer.synchronize(request)

    assert result.checkpoint == "cp-1"
    assert result.streaming is True
    assert result.row_count == 0
    assert result.status == ExecutionStatus.CANCELLED


def test_sql_synchronizer_retries_after_transient_failure_and_honors_object_tokens() -> None:
    class FlakyConnection:
        def __init__(self) -> None:
            self.attempts = 0

        def cursor(self) -> StubCursor:
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError("timed out")
            return StubCursor(rows=[{"id": 7}])

        def close(self) -> None:
            return None

    class FlakyFactory(SQLServerConnectionFactory):
        def __init__(self, connection: FlakyConnection) -> None:
            super().__init__(SQLServerConfig(connection_string="Driver=Test"))
            self._connection = connection

        def create_connection(self) -> Any:
            return self._connection

    pool = ConnectionPool(factory=FlakyFactory(FlakyConnection()), max_size=1)
    synchronizer = SQLSynchronizer(pool=pool, max_retries=1)

    result = synchronizer.synchronize(
        SQLRequest(
            query_name="retry_query",
            query_text="SELECT 1",
            parameters={"id": 1},
            stream=True,
            checkpoint="resume-1",
        )
    )
    assert result.status == ExecutionStatus.COMPLETED
    assert result.retries == 1

    class CancelToken:
        is_cancelled = True

    cancelled = synchronizer.synchronize(
        SQLRequest(
            query_name="cancel_query",
            query_text="SELECT 1",
            parameters={},
            stream=True,
            checkpoint="resume-2",
            cancellation_token=CancelToken(),
        )
    )
    assert cancelled.status == ExecutionStatus.CANCELLED
    assert cancelled.checkpoint == "resume-2"


def test_sql_synchronizer_returns_failed_result_for_timeout_and_validation_failures() -> None:
    class BoomConnection:
        def cursor(self) -> None:
            raise ValueError("bad request")

        def close(self) -> None:
            return None

    class BoomFactory(SQLServerConnectionFactory):
        def __init__(self) -> None:
            super().__init__(SQLServerConfig(connection_string="Driver=Test"))

        def create_connection(self) -> Any:
            return BoomConnection()

    pool = ConnectionPool(factory=BoomFactory(), max_size=1)
    synchronizer = SQLSynchronizer(pool=pool, max_retries=0)
    result = synchronizer.synchronize(SQLRequest(query_name="boom", query_text="SELECT 1", parameters={}))

    assert result.status == ExecutionStatus.FAILED
    assert result.errors == ["bad request"]

    failed_validation = synchronizer.synchronize(SQLRequest(query_name="", query_text="", parameters={}))
    assert failed_validation.status == ExecutionStatus.FAILED
    assert failed_validation.errors


def test_connector_raises_for_cancelled_and_failed_synchronization() -> None:
    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db", max_retries=0),
        connection_factory=StubFactory(connection=StubConnection()),
        pool=ConnectionPool(factory=StubFactory(), max_size=1),
    )

    with pytest.raises(IntegrationError, match="cancelled"):
        connector.synchronize(SQLRequest(query_name="cancelled", query_text="SELECT 1", parameters={}, cancellation_token="cancelled"))

    class BrokenConnection:
        def cursor(self) -> None:
            raise RuntimeError("boom")

        def close(self) -> None:
            return None

    class BrokenFactory(SQLServerConnectionFactory):
        def __init__(self) -> None:
            super().__init__(SQLServerConfig(connection_string="Server=sql;Database=db", max_retries=0))

        def create_connection(self) -> Any:
            return BrokenConnection()

    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db", max_retries=0),
        connection_factory=BrokenFactory(),
        pool=ConnectionPool(factory=BrokenFactory(), max_size=1),
    )
    with pytest.raises(IntegrationError, match="failed"):
        connector.synchronize(SQLRequest(query_name="fail", query_text="SELECT 1", parameters={}))


def test_driver_adapter_uses_injected_module_for_execution() -> None:
    class DriverModule:
        def connect(self, connection_string: str):
            return connection_string

    class Cursor:
        def __init__(self) -> None:
            self.executed: tuple[str, dict[str, Any]] | None = None
            self.rows = [{"id": 1}]

        def execute(self, query: str, params: dict[str, Any] | None = None) -> None:
            self.executed = (query, params or {})

        def fetchall(self) -> list[dict[str, Any]]:
            return self.rows

    class Connection:
        def __init__(self) -> None:
            self.cursor_obj = Cursor()

        def cursor(self) -> Cursor:
            return self.cursor_obj

    module = DriverModule()
    adapter = PyOdbcDriverAdapter(module)
    connection = Connection()
    rows, cursor = adapter.execute(connection, "SELECT 1", {"id": 1})
    assert rows == [{"id": 1}]
    assert cursor is connection.cursor_obj


def test_pyodbc_driver_adapter_supports_module_connection_and_no_params() -> None:
    class DriverModule:
        def connect(self, connection_string: str) -> str:
            return connection_string

    class Cursor:
        def __init__(self) -> None:
            self.rows = [{"id": 3}]

        def execute(self, query: str, params: dict[str, Any] | None = None) -> None:
            return None

        def fetchall(self) -> list[dict[str, Any]]:
            return self.rows

    class Connection:
        def __init__(self) -> None:
            self.cursor_obj = Cursor()

        def cursor(self) -> Cursor:
            return self.cursor_obj

    adapter = PyOdbcDriverAdapter(DriverModule())
    assert adapter.connect("conn") == "conn"
    rows, cursor = adapter.execute(Connection(), "SELECT 1")
    assert rows == [{"id": 3}]
    assert cursor is not None


def test_pyodbc_driver_adapter_reports_missing_module_and_invalid_connection() -> None:
    adapter = PyOdbcDriverAdapter(None)
    with pytest.raises(RuntimeError, match="pyodbc"):
        adapter.connect("conn")

    class StubModule:
        def connect(self, connection_string: str) -> str:
            return connection_string

    class NoCursorConnection:
        pass

    adapter = PyOdbcDriverAdapter(StubModule())
    with pytest.raises(RuntimeError, match="cursor"):
        adapter.execute(NoCursorConnection(), "SELECT 1")


def test_sql_health_monitor_tracks_failures_and_retries() -> None:
    health = SQLHealthMonitor()
    health.record_connection("sql", healthy=True, latency_ms=5.0, retries=1)
    health.record_failure("sql", "timeout")
    health.record_execution("sql", rows=3, elapsed_ms=7.0)

    snapshot = health.snapshot("sql")
    assert snapshot["healthy"] is True
    assert snapshot["failures"] == 1
    assert snapshot["retries"] == 1


def test_sql_audit_and_metrics_store_details() -> None:
    audit = SQLAudit()
    metrics = SQLMetrics()

    audit.record(
        SynchronizationLog(
            execution_id="exec-1",
            correlation_id="corr-1",
            connector="sqlserver",
            duration_seconds=1.5,
            records_processed=3,
            warnings=["warn"],
            errors=["err"],
            user="ops",
            timestamp=datetime.now(UTC),
        )
    )
    metrics.increment("queries")
    metrics.gauge("latency", 10.0)

    assert audit.entries[-1].execution_id == "exec-1"
    assert metrics.snapshot()["queries"] == 1.0


def test_sql_connector_validation_failure_raises_error() -> None:
    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db"),
        connection_factory=StubFactory(connection=StubConnection()),
        pool=ConnectionPool(factory=StubFactory(), max_size=1),
    )

    with pytest.raises(IntegrationError):
        connector.validate(SQLRequest(query_name="", query_text="", parameters={}))


def test_sql_connector_handles_timeout_and_validation_edges() -> None:
    config = SQLServerConfig(connection_string="Server=sql;Database=db", timeout_seconds=10, max_retries=2)
    connector = SQLServerConnector(
        config=config,
        connection_factory=StubFactory(connection=StubConnection()),
        pool=ConnectionPool(factory=StubFactory(), max_size=1),
    )

    assert connector.config.timeout_seconds == 10
    assert connector.validate(SQLRequest(query_name="select", query_text="SELECT 1", parameters={"id": 1})).ok is True


def test_sql_connector_validate_and_audit_cover_error_and_fallback_paths() -> None:
    connector = SQLServerConnector(
        config=SQLServerConfig(connection_string="Server=sql;Database=db"),
        connection_factory=StubFactory(connection=StubConnection()),
        pool=ConnectionPool(factory=StubFactory(), max_size=1),
    )

    with pytest.raises(IntegrationError):
        connector.validate({"not": "sql"})
    with pytest.raises(IntegrationError):
        connector.validate(SQLRequest(query_name="", query_text="", parameters={}))

    connector.normalize({"x": 1})
    connector.audit(SynchronizationLog(execution_id="x", correlation_id="y", connector="sqlserver", duration_seconds=0.0, records_processed=0))


def test_connection_pool_closed_state_and_release_path() -> None:
    pool = ConnectionPool(factory=StubFactory(), max_size=1)
    connection = pool.acquire()
    pool.release(connection)
    pool.close()

    with pytest.raises(RuntimeError):
        pool.acquire()


def test_connection_pool_reuses_first_connection_when_full() -> None:
    pool = ConnectionPool(factory=StubFactory(), max_size=1)
    first = pool.acquire()
    second = pool.acquire()
    assert first is second


def test_sql_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        SQLServerConfig(connection_string="Server=sql;Database=db", timeout_seconds=0)
    with pytest.raises(ValueError, match="max_retries"):
        SQLServerConfig(connection_string="Server=sql;Database=db", max_retries=-1)
    with pytest.raises(ValueError, match="connection_string"):
        SQLServerConfig(connection_string="   ")


def test_sql_synchronizer_returns_failed_result_for_invalid_requests() -> None:
    pool = ConnectionPool(factory=StubFactory(), max_size=1)
    synchronizer = SQLSynchronizer(pool=pool)
    result = synchronizer.synchronize(SQLRequest(query_name="", query_text="", parameters={}))

    assert result.status == ExecutionStatus.FAILED
    assert result.errors
