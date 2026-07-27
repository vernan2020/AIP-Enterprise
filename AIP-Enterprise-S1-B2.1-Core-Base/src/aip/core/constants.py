from __future__ import annotations

from enum import StrEnum


class EnvironmentName(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class CurrencyCode(StrEnum):
    CRC = "CRC"
    USD = "USD"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    EXPORT = "EXPORT"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


DEFAULT_TIMEZONE = "America/Costa_Rica"
DEFAULT_LOCALE = "es_CR"
APPLICATION_CODE = "AIP"
