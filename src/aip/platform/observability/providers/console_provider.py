from __future__ import annotations

import json
import sys

from aip.platform.observability.logging.structured_log import StructuredLog


class ConsoleProvider:
    def emit(self, log: StructuredLog) -> None:
        print(json.dumps(log.to_dict()), file=sys.stdout)
