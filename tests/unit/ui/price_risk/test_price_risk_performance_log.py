from __future__ import annotations

import logging
from time import perf_counter

from aip.ui.modules.price_risk.performance_log import record_stage_duration


def test_price_risk_profile_is_opt_in(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AIP_PRICE_RISK_PROFILE", raising=False)
    record_stage_duration("portfolio_load", perf_counter())
    assert not (tmp_path / "logs" / "price_risk_performance.log").exists()


def test_price_risk_profile_writes_timings_without_financial_data(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AIP_PRICE_RISK_PROFILE", "1")
    logger = logging.getLogger("aip.price_risk.performance")
    for handler in tuple(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    try:
        record_stage_duration("var_calculation", perf_counter())
        log_path = tmp_path / "logs" / "price_risk_performance.log"
        assert log_path.is_file()
        contents = log_path.read_text(encoding="utf-8")
        assert "stage=var_calculation duration_ms=" in contents
    finally:
        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
