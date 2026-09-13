from __future__ import annotations

import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    path = root / "src" / "aip" / "ui" / "modules" / "macro_intelligence" / "views" / "macro_intelligence_view.py"
    text = path.read_text(encoding="utf-8")

    marker = "MacroProjectionPanel(application_factory=self._application_factory"
    if marker in text:
        print("Macro projection UI already enabled")
        return 0

    pattern = re.compile(
        r"    def _build_projection_section\(\n"
        r"        self,\n"
        r"    \) -> QWidget:\n"
        r".*?"
        r"        return group\n\n"
        r"    def _build_middle_section\(",
        re.DOTALL,
    )

    replacement = '''    def _build_projection_section(\n        self,\n    ) -> QWidget:\n        from aip.ui.modules.macro_intelligence.widgets.macro_projection_panel import (\n            MacroProjectionPanel,\n        )\n\n        return MacroProjectionPanel(\n            application_factory=self._application_factory,\n            parent=self,\n        )\n\n    def _build_middle_section('''

    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Unable to patch MacroIntelligenceView projection section")

    updated = updated.replace(
        'self._scenario_combo.setToolTip("Disponible cuando se implemente " "Scenario Engine.")',
        'self._scenario_combo.setToolTip("Escenario institucional gobernado; BASE aprobado en el repositorio.")',
    )
    updated = updated.replace(
        'self._simulate_button.setToolTip("Pendiente del motor econométrico.")',
        'self._simulate_button.setToolTip("La trayectoria aprobada se muestra en la tabla institucional.")',
    )

    path.write_text(updated, encoding="utf-8")
    compile(updated, str(path), "exec")
    print("Macro projection UI enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
