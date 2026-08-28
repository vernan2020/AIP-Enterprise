from __future__ import annotations

from datetime import date
from threading import RLock


class ValuationDateContext:
    """Thread-safe session context for the active institutional valuation date.

    The context is deliberately independent from the Qt/UI layer so configured
    application services can share one authoritative cutoff without rebuilding
    the dependency container.
    """

    def __init__(self, initial_date: date) -> None:
        if not isinstance(initial_date, date):
            raise TypeError("initial_date must be datetime.date")
        self._value = initial_date
        self._lock = RLock()

    @property
    def value(self) -> date:
        with self._lock:
            return self._value

    def set(self, value: date) -> bool:
        if not isinstance(value, date):
            raise TypeError("value must be datetime.date")
        with self._lock:
            if value == self._value:
                return False
            self._value = value
            return True
