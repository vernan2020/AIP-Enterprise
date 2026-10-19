from __future__ import annotations

from aip.tools.preflight_runtime import _bccr_live_status


def test_bccr_live_status_requires_non_blank_token() -> None:
    assert _bccr_live_status(None) == "TOKEN MISSING · LOCAL-HISTORY FALLBACK"
    assert _bccr_live_status("") == "TOKEN MISSING · LOCAL-HISTORY FALLBACK"
    assert _bccr_live_status("   ") == "TOKEN MISSING · LOCAL-HISTORY FALLBACK"
    assert _bccr_live_status("token-value") == "READY"
