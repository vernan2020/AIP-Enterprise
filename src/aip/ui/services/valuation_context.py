from __future__ import annotations

from datetime import date

from PySide6.QtCore import QObject, Signal

from aip.product.configured.context.valuation_date_context import (
    ValuationDateContext,
)


class ValuationContext(QObject):
    """Qt adapter for the authoritative application valuation-date context.

    In CONFIGURED mode the adapter wraps the ``ValuationDateContext`` instance
    registered in the application container.  It therefore does not own a
    second valuation date; it only exposes the shared runtime value to Qt and
    emits UI notifications when that authoritative value changes.

    In non-CONFIGURED/test usage a private ``ValuationDateContext`` is created
    to preserve the existing constructor contract.
    """

    valuation_date_changed = Signal(object)

    def __init__(
        self,
        initial_date: date,
        parent: QObject | None = None,
        *,
        source_context: ValuationDateContext | None = None,
    ) -> None:
        super().__init__(parent)

        if not isinstance(initial_date, date):
            raise TypeError("initial_date must be datetime.date")

        self._source_context = (
            source_context
            if source_context is not None
            else ValuationDateContext(initial_date)
        )
        self._last_notified_date = self._source_context.value

    @property
    def valuation_date(self) -> date:
        """Return the authoritative active valuation date."""
        return self._source_context.value

    @property
    def source_context(self) -> ValuationDateContext:
        """Expose the wrapped application context for identity diagnostics."""
        return self._source_context

    def set_valuation_date(self, value: date) -> bool:
        """Update/notify the active valuation date.

        The underlying application context is authoritative.  The additional
        ``_last_notified_date`` value is only Qt notification bookkeeping; it
        is not used by application services to determine the active cutoff.

        ``DemoApplicationFactory.set_data_cutoff_date`` may commit the shared
        context immediately before this adapter is called.  In that case the
        source ``set`` is a no-op but this method still emits exactly one Qt
        notification because the new value has not yet been announced to the
        UI.
        """
        if not isinstance(value, date):
            raise TypeError("value must be datetime.date")

        source_changed = self._source_context.set(value)
        notification_changed = value != self._last_notified_date

        if not source_changed and not notification_changed:
            return False

        self._last_notified_date = value
        self.valuation_date_changed.emit(value)
        return True

    def reset(self, value: date) -> None:
        """Reset the active date through the authoritative context."""
        self.set_valuation_date(value)
