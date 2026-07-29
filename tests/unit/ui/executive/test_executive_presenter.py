from __future__ import annotations

from aip.ui.modules.executive.presenters.executive_presenter import ExecutivePresenter


def test_executive_presenter_builds_view_model() -> None:
    presenter = ExecutivePresenter()
    view_model = presenter.build_view_model()
    assert view_model.status == "loaded"
    assert view_model.summary[0].startswith("Portfolio Market Value")
    assert view_model.recommendations[0].title == "Treasury Buffer Review"
