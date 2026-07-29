from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from aip.integration.audit.synchronization_log import SynchronizationLog
from aip.integration.contracts.synchronization import SynchronizationRequest
from aip.integration.normalization.normalizer import Normalizer
from aip.integration.validation.validator import ValidationResult, Validator


class ConnectorType(str, Enum):
    """Supported connector families for the integration platform."""

    SQL_SERVER = "sql_server"
    FOLDER_WATCH = "folder_watch"
    REST_API = "rest_api"
    FILE_IMPORT = "file_import"
    FUTURE = "future"


@runtime_checkable
class ConnectorProtocol(Protocol):
    """Infrastructure contract for every external connector."""

    name: str

    def connect(self) -> None:
        """Connect to the underlying source."""

    def disconnect(self) -> None:
        """Disconnect from the underlying source."""

    def health(self) -> bool:
        """Return whether the connector is healthy."""

    def synchronize(self, request: SynchronizationRequest) -> int:
        """Synchronize records and return the number of records processed."""

    def validate(self, payload: object) -> ValidationResult:
        """Validate a payload before synchronization."""

    def normalize(self, payload: object) -> object:
        """Normalize the payload into a platform-safe representation."""

    def audit(self, log: SynchronizationLog) -> None:
        """Persist audit metadata for the execution."""


@dataclass(frozen=True, slots=True)
class ConnectorDescriptor:
    """Metadata describing an available connector."""

    name: str
    connector_type: ConnectorType
    description: str


class Connector(ABC):
    """Base class for integration connectors that provides a default validator and normalizer."""

    name: str = ""
    description: str = ""
    connector_type: ConnectorType = ConnectorType.FUTURE

    @abstractmethod
    def connect(self) -> None:
        """Establish connectivity to the external endpoint."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release connectivity to the external endpoint."""

    @abstractmethod
    def health(self) -> bool:
        """Return whether the connector is healthy."""

    @abstractmethod
    def synchronize(self, request: SynchronizationRequest) -> int:
        """Synchronize data from the connector into the platform."""

    @abstractmethod
    def validate(self, payload: object) -> ValidationResult:
        """Validate a payload against connector-specific rules."""

    @abstractmethod
    def normalize(self, payload: object) -> object:
        """Normalize the connector payload into a platform-safe representation."""

    @abstractmethod
    def audit(self, log: SynchronizationLog) -> None:
        """Record execution details for the connector."""

    def validator(self) -> Validator:
        """Return the default validator instance for the connector."""

        return Validator()

    def normalizer(self) -> Normalizer:
        """Return the default normalizer instance for the connector."""

        return Normalizer()
