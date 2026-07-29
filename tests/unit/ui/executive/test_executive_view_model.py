from __future__ import annotations

from aip.ui.modules.executive.viewmodels.executive_view_model import ExecutiveViewModel


def test_executive_view_model_is_immutable_and_serializable() -> None:
    view_model = ExecutiveViewModel(summary=("A",), portfolio=("B",), liquidity=("C",), market=("D",), recommendations=(), alerts=(), trends=(("30 Days", ("1", "2")),))
    assert view_model.to_dict()["summary"] == ["A"]
    assert view_model.to_dict()["trends"][0]["label"] == "30 Days"
