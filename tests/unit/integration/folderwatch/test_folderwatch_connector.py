from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aip.integration.audit.execution_result import ExecutionStatus
from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.connector import ConnectorType
from aip.integration.events.synchronization_events import IntegrationEventBus, SynchronizationEvent, SynchronizationEventType
from aip.integration.exceptions.exceptions import IntegrationError
from aip.integration.folderwatch.audit.folder_audit import FolderAudit
from aip.integration.folderwatch.checkpoint_store import InMemoryCheckpointStore
from aip.integration.folderwatch.configuration.folder_config import FolderWatchConfig
from aip.integration.folderwatch.connector.folder_connector import FolderWatchConnector
from aip.integration.folderwatch.connector.watcher import FolderWatcher
from aip.integration.folderwatch.contracts.file_request import FileRequest
from aip.integration.folderwatch.contracts.file_result import FileExecutionResult
from aip.integration.folderwatch.events.folder_events import FolderWatchEvent, FolderWatchEventType
from aip.integration.folderwatch.monitoring.folder_health import FolderHealthMonitor
from aip.integration.folderwatch.normalization.file_normalizer import FileNormalizer
from aip.integration.folderwatch.providers.filesystem_provider import FileSystemProvider
from aip.integration.folderwatch.providers.local_filesystem_provider import LocalFileSystemProvider
from aip.integration.folderwatch.synchronization.folder_synchronizer import FolderSynchronizer
from aip.integration.folderwatch.telemetry.folder_metrics import FolderMetrics
from aip.integration.folderwatch.validation.file_validator import FileValidator


@dataclass
class FakeFileSystemProvider(FileSystemProvider):
    files: list[dict[str, Any]] = field(default_factory=list)
    scanned: list[Path] = field(default_factory=list)

    def list_files(self, path: str, *, recursive: bool = False) -> list[dict[str, Any]]:
        self.scanned.append(Path(path))
        return list(self.files)

    def exists(self, path: str) -> bool:
        return True

    def is_file(self, path: str) -> bool:
        return True

    def read_bytes(self, path: str) -> bytes:
        return b"payload"

    def stat(self, path: str) -> dict[str, Any]:
        return {"size": 10, "modified": datetime.now(UTC)}


def test_folder_config_validates_and_safely_repr() -> None:
    config = FolderWatchConfig(folder_paths=["/tmp/inbox"], extensions=[".txt"], recursive=True, min_size=1, max_size=10)
    assert config.folder_paths == ["/tmp/inbox"]
    assert config.recursive is True
    assert "secret" not in repr(config)

    with pytest.raises(ValueError):
        FolderWatchConfig(folder_paths=[], extensions=[".txt"])
    with pytest.raises(ValueError):
        FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"], min_size=-1)
    with pytest.raises(ValueError):
        FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"], max_size=0)
    with pytest.raises(ValueError):
        FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"], min_size=10, max_size=5)
    with pytest.raises(ValueError):
        FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"], poll_interval_seconds=0)


def test_file_validator_accepts_and_rejects_expected_inputs() -> None:
    validator = FileValidator()
    valid = validator.validate(FileRequest(path="/tmp/test.txt", filename="test.txt", extension=".txt", size=3))
    assert valid.ok is True

    invalid = validator.validate(FileRequest(path="", filename="", extension="", size=0))
    assert invalid.ok is False


def test_file_normalizer_returns_generic_metadata() -> None:
    normalizer = FileNormalizer()
    result = normalizer.normalize({"path": "/tmp/sample.txt", "filename": "sample.txt"})
    assert result["path"] == "/tmp/sample.txt"
    assert result["filename"] == "sample.txt"

    scalar = normalizer.normalize("plain")
    assert scalar["value"] == "plain"


def test_checkpoint_store_persists_and_resumes() -> None:
    store = InMemoryCheckpointStore()
    store.save("job-1", "file-1", {"hash": "abc"})
    assert store.get("job-1", "file-1") == {"hash": "abc"}
    assert store.list("job-1") == ["file-1"]


def test_folder_watcher_starts_stops_and_detects_files() -> None:
    provider = FakeFileSystemProvider(files=[{"path": "/tmp/one.txt", "filename": "one.txt", "extension": ".txt", "size": 4}])
    watcher = FolderWatcher(provider=provider, config=FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"], recursive=True))
    watcher.start()
    detected = watcher.scan_once()
    watcher.stop()
    assert detected[0].filename == "one.txt"
    assert watcher.state == "stopped"

    filtered = watcher._matches_filters("/tmp/.hidden", ".hidden", ".txt", 4)
    assert filtered is False

    filtered_temp = watcher._matches_filters("/tmp/~temp", "~temp", ".txt", 4)
    assert filtered_temp is False

    filtered_size = watcher._matches_filters("/tmp/large.txt", "large.txt", ".txt", 1000)
    assert filtered_size is True


def test_folder_watcher_matches_filename_patterns_and_regex() -> None:
    watcher = FolderWatcher(
        provider=FakeFileSystemProvider(),
        config=FolderWatchConfig(
            folder_paths=["/tmp"],
            extensions=[".txt"],
            filename_patterns=["report"],
            regex_patterns=[r"^log"],
            recursive=False,
            max_size=100,
        ),
    )
    assert watcher._matches_filters("/tmp/other.txt", "other.txt", ".txt", 5) is False
    assert watcher._matches_filters("/tmp/report.txt", "report.txt", ".txt", 5) is True
    assert watcher._matches_filters("/tmp/log.txt", "log.txt", ".txt", 5) is True


def test_folder_synchronizer_processes_and_retries() -> None:
    provider = FakeFileSystemProvider(files=[{"path": "/tmp/one.txt", "filename": "one.txt"}])
    synchronizer = FolderSynchronizer(provider=provider, validator=FileValidator(), normalizer=FileNormalizer(), max_retries=1)
    result = synchronizer.synchronize([FileRequest(path="/tmp/one.txt", filename="one.txt", extension=".txt", size=10)])
    assert result.status == ExecutionStatus.COMPLETED
    assert result.records_processed == 1

    failure = synchronizer.synchronize([FileRequest(path="", filename="", extension="", size=0)])
    assert failure.status == ExecutionStatus.FAILED

    empty = synchronizer.synchronize([])
    assert empty.status == ExecutionStatus.FAILED


def test_folder_connector_lifecycle_and_events() -> None:
    provider = FakeFileSystemProvider(files=[{"path": "/tmp/one.txt", "filename": "one.txt"}])
    event_bus = IntegrationEventBus()
    events: list[SynchronizationEvent] = []
    event_bus.subscribe(events.append)
    connector = FolderWatchConnector(
        config=FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"]),
        provider=provider,
        event_bus=event_bus,
    )
    connector.connect()
    assert connector.health() is True
    connector.disconnect()
    assert connector.health() is False
    assert any(event.event_type == SynchronizationEventType.CONNECTED for event in events)

    result = connector.synchronize(FileRequest(path="/tmp/one.txt", filename="one.txt", extension=".txt", size=10), correlation_id="corr")
    assert result.status == ExecutionStatus.COMPLETED

    with pytest.raises(IntegrationError, match="Validation failed"):
        connector.synchronize(FileRequest(path="/tmp/one.txt", filename="one.txt", extension=".txt", size=0), correlation_id="corr")


def test_folder_connector_validation_and_audit_paths() -> None:
    provider = FakeFileSystemProvider(files=[{"path": "/tmp/one.txt", "filename": "one.txt"}])
    connector = FolderWatchConnector(config=FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"]), provider=provider)
    with pytest.raises(IntegrationError):
        connector.validate({"not": "file"})
    log = SynchronizationLog(execution_id="exec-1", correlation_id="corr-1", connector="folderwatch", duration_seconds=0.0, records_processed=0, user="ops", timestamp=datetime.now(UTC))
    connector.audit(log)
    assert connector.health() is False
    assert connector.normalize(FileRequest(path="/tmp/one.txt", filename="one.txt", extension=".txt", size=1))["filename"] == "one.txt"
    assert connector.normalize("plain")["value"] == "plain"


def test_folder_connector_synchronize_with_cancellation() -> None:
    provider = FakeFileSystemProvider(files=[{"path": "/tmp/one.txt", "filename": "one.txt"}])
    connector = FolderWatchConnector(config=FolderWatchConfig(folder_paths=["/tmp"], extensions=[".txt"]), provider=provider)
    with pytest.raises(IntegrationError, match="cancelled"):
        connector.synchronize(FileRequest(path="/tmp/one.txt", filename="one.txt", extension=".txt", size=10), correlation_id="corr", cancellation_token="cancelled")


def test_folder_health_monitor_and_metrics() -> None:
    monitor = FolderHealthMonitor()
    monitor.record_detection("folder", 2)
    monitor.record_processed("folder", 1)
    monitor.record_failure("folder")
    monitor.record_retry("folder")
    monitor.record_latency("folder", 4.5)
    monitor.record_state("folder", "running")
    snapshot = monitor.snapshot("folder")
    assert snapshot["files_detected"] == 2
    assert snapshot["files_processed"] == 1
    assert snapshot["state"] == "running"

    metrics = FolderMetrics()
    metrics.increment("files")
    metrics.gauge("latency", 3.0)
    assert metrics.snapshot()["files"] == 1.0


def test_folder_audit_and_folder_events() -> None:
    audit = FolderAudit()
    event_bus = IntegrationEventBus()
    events: list[FolderWatchEvent] = []
    event_bus.subscribe(lambda event: events.append(event))
    audit.record(SynchronizationLog(execution_id="exec-2", correlation_id="corr-2", connector="folderwatch", duration_seconds=0.0, records_processed=0, user="ops", timestamp=datetime.now(UTC)))
    event = FolderWatchEvent.started("job", "folderwatch", "exec-2")
    assert event.event_type == FolderWatchEventType.STARTED
    assert FolderWatchEvent.stopped("job", "folderwatch", "exec-2").event_type == FolderWatchEventType.STOPPED
    assert FolderWatchEvent.detected("job", "folderwatch", "exec-2", "file.txt").details["filename"] == "file.txt"
    assert FolderWatchEvent.processing_started("job", "folderwatch", "exec-2", "file.txt").details["filename"] == "file.txt"
    assert FolderWatchEvent.processing_completed("job", "folderwatch", "exec-2", "file.txt").details["filename"] == "file.txt"
    assert FolderWatchEvent.processing_failed("job", "folderwatch", "exec-2", "file.txt", "boom").details["error"] == "boom"
    assert FolderWatchEvent.retry_started("job", "folderwatch", "exec-2", 2).details["attempt"] == 2
    assert FolderWatchEvent.retry_completed("job", "folderwatch", "exec-2", 2).details["attempt"] == 2


def test_local_filesystem_provider_works(tmp_path: Path) -> None:
    provider = LocalFileSystemProvider()
    assert provider.exists("/tmp") is True
    assert provider.is_file("/tmp") is False
    assert provider.read_bytes("/etc/hosts") is not None
    metadata = provider.stat("/etc/hosts")
    assert metadata["size"] >= 0

    nested_file = tmp_path / "nested" / "sample.txt"
    nested_file.parent.mkdir(parents=True, exist_ok=True)
    nested_file.write_text("hello")
    assert provider.list_files(str(tmp_path), recursive=False) == [] or provider.list_files(str(tmp_path), recursive=False)[0]["filename"] == "sample.txt"
    recursive = provider.list_files(str(tmp_path), recursive=True)
    assert recursive[0]["filename"] == "sample.txt"
    assert provider.exists(str(nested_file)) is True
    assert provider.is_file(str(nested_file)) is True
