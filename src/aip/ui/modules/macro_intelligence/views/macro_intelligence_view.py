from __future__ import annotations

from aip.ui.modules.macro_intelligence.views.macro_intelligence_workspace import (
    MacroIntelligenceWorkspace,
)


class MacroIntelligenceView(MacroIntelligenceWorkspace):
    """Backward-compatible route name for the advanced Macro Intelligence workspace."""


__all__ = ["MacroIntelligenceView", "MacroIntelligenceWorkspace"]
