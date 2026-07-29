from __future__ import annotations

from aip.ui.modules.executive.views.executive_workspace import ExecutiveWorkspace


def test_theme_switching_updates_executive_workspace(qt_app) -> None:
    workspace = ExecutiveWorkspace()
    workspace.bind_view_model(workspace.view_model())
    assert workspace.view_model().theme_name == "light"
