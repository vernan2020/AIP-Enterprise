from datetime import date
from types import SimpleNamespace

from aip.ui.modules.macro_intelligence.freshness import economic_source_freshness_notice


def test_http_500_macro_notice_is_explicit_and_does_not_blame_token() -> None:
    snapshot = SimpleNamespace(
        market_snapshot=(),
        source="BCCR · HISTÓRICO LOCAL",
        diagnostics=("Live BCCR unavailable: FX: HTTP 500",),
    )
    notice = economic_source_freshness_notice(snapshot, as_of=date(2026, 10, 28))
    assert "HTTP 500" in notice
    assert "No hay observaciones históricas disponibles" in notice
    assert "causa no está confirmada" in notice
    assert "temporalmente no disponible" not in notice
    assert "Revisar token" not in notice
