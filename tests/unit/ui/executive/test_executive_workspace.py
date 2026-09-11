from __future__ import annotations

from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace


def test_executive_workspace_renders_and_binds(qt_app) -> None:
    workspace = ExecutiveWorkspace()
    assert workspace.view_model().status == "loaded"
    assert workspace.view_model().summary[0].startswith("Portafolio:")
