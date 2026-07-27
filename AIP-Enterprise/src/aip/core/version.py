from __future__ import annotations
from dataclasses import dataclass

APP_NAME = "AIP Enterprise"
APP_VERSION = "0.1.0"
APP_RELEASE = "R0.1.0"
ORGANIZATION = "Coopealianza R.L."


@dataclass(frozen=True, slots=True)
class VersionInfo:
    name: str = APP_NAME
    version: str = APP_VERSION
    release: str = APP_RELEASE
    organization: str = ORGANIZATION


VERSION = VersionInfo()
