from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, NoReturn, TypeVar, cast

from aip.core.exceptions import AIPError

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Resultado explícito de una operación que puede fallar de forma controlada."""

    _value: T | None = None
    _error: AIPError | None = None

    def __post_init__(self) -> None:
        if (self._value is None) == (self._error is None):
            raise ValueError("Result debe contener exactamente un valor o un error.")

    @classmethod
    def success(cls, value: T) -> "Result[T]":
        return cls(_value=value)

    @classmethod
    def failure(cls, error: AIPError) -> "Result[T]":
        return cls(_error=error)

    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_failure(self) -> bool:
        return self._error is not None

    @property
    def value(self) -> T:
        if self._error is not None:
            self._raise_error()
        return cast(T, self._value)

    @property
    def error(self) -> AIPError:
        if self._error is None:
            raise RuntimeError("Un resultado exitoso no contiene error.")
        return self._error

    def unwrap_or(self, default: T) -> T:
        return self.value if self.is_success else default

    def map(self, transform: Callable[[T], U]) -> "Result[U]":
        if self.is_failure:
            return Result.failure(self.error)
        return Result.success(transform(self.value))

    def bind(self, transform: Callable[[T], "Result[U]"]) -> "Result[U]":
        if self.is_failure:
            return Result.failure(self.error)
        return transform(self.value)

    def _raise_error(self) -> NoReturn:
        raise self.error
