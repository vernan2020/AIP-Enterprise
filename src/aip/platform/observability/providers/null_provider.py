from __future__ import annotations

from aip.platform.observability.logging.structured_log import StructuredLog


class NullProvider:
    def emit(self, log: StructuredLog) -> None:
        return None
