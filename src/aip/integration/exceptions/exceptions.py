from __future__ import annotations

from aip.core.exceptions import AIPError


class IntegrationError(AIPError):
    """Raised when the integration platform encounters a runtime issue."""

    default_code = "INTEGRATION_ERROR"
