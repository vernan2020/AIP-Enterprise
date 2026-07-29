from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")


class ServiceNotRegisteredError(KeyError):
    pass


class Container:
    def __init__(self) -> None:
        self._instances: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[["Container"], Any]] = {}

    def register_instance(self, service_type: type[T], instance: T) -> None:
        self._instances[service_type] = instance

    def register_factory(self, service_type: type[T], factory: Callable[["Container"], T]) -> None:
        self._factories[service_type] = factory

    def resolve(self, service_type: type[T]) -> T:
        if service_type in self._instances:
            return cast(T, self._instances[service_type])
        factory = self._factories.get(service_type)
        if factory is None:
            raise ServiceNotRegisteredError(service_type.__name__)
        instance = factory(self)
        self._instances[service_type] = instance
        return cast(T, instance)
