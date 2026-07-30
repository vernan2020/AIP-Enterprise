from __future__ import annotations

from typing import Any


class DemoHealthProvider:
    """Provides deterministic health state for the demo runtime."""

    def get_health(self) -> dict[str, Any]:
        return {
            "sql_server": "HEALTHY",
            "folder_watch": "HEALTHY",
            "bccr": "HEALTHY",
            "integration_hub": "HEALTHY",
            "data_quality": "HEALTHY",
            "scheduler": "HEALTHY",
            "notifications": "HEALTHY",
            "observability": "HEALTHY",
            "security": "HEALTHY",
        }
