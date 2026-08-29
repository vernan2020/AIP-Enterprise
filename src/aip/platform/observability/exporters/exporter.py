from __future__ import annotations

from typing import Protocol

from aip.platform.observability.logging.structured_log import StructuredLog


class Exporter(Protocol):
    def export(self, log: StructuredLog) -> None: ...
