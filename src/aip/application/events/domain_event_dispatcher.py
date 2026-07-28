from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aip.application.exceptions import EventDispatchError


class DomainEventDispatcher:
    """Minimal domain-event dispatcher for application workflow lifecycle hooks."""

    def __init__(self, *, raise_on_error: bool = True) -> None:
        self._raise_on_error = raise_on_error
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {
            "pre_workflow": [],
            "post_workflow": [],
            "workflow_failed": [],
        }

    def subscribe(self, event_name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        if handler not in self._handlers.setdefault(event_name, []):
            self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        handlers = self._handlers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    def dispatch(self, event_name: str, payload: dict[str, Any]) -> None:
        for handler in list(self._handlers.get(event_name, ())):
            try:
                handler(payload)
            except Exception as exc:
                if self._raise_on_error:
                    raise EventDispatchError(str(exc)) from exc
