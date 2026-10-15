from __future__ import annotations

from importlib.util import find_spec

from aip.integration.bccr.providers.http_provider import HTTPProvider
from aip.integration.bccr.providers.httpx_http_provider import HttpxHTTPProvider
from aip.integration.bccr.providers.urllib_http_provider import UrllibHTTPProvider


def select_official_bccr_transport() -> HTTPProvider:
    """Use TicoTrader-compatible httpx when installed; retain safe legacy fallback.

    PREVIEW may already have a pre-existing virtual environment. A newly
    installed source tree must not become unbootable just because the additional
    HTTP dependency has not yet been installed on the institutional workstation.
    """
    if find_spec("httpx") is not None:
        return HttpxHTTPProvider()
    return UrllibHTTPProvider()
