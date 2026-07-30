from __future__ import annotations

from dataclasses import dataclass

APP_NAME = "AIP Enterprise"
APP_VERSION = "1.0.0-rc1"
APP_RELEASE = "RC1"
APP_DISPLAY_NAME = "AIP Enterprise — DEMO MODE"
APP_DISPLAY_VERSION = "AIP Enterprise 1.0.0 RC1"
ORGANIZATION = "Coopealianza R.L."


@dataclass(frozen=True, slots=True)
class VersionInfo:
    name: str = APP_NAME
    version: str = APP_VERSION
    release: str = APP_RELEASE
    display_name: str = APP_DISPLAY_NAME
    display_version: str = APP_DISPLAY_VERSION
    organization: str = ORGANIZATION


VERSION = VersionInfo()
