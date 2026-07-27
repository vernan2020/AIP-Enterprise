from __future__ import annotations

from enum import Enum


class OutlierMethod(str, Enum):
    """Supported outlier detection methods."""

    IQR = "iqr"
    Z_SCORE = "z_score"
    MODIFIED_Z_SCORE = "modified_z_score"
