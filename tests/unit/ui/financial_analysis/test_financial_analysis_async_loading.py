from __future__ import annotations

import threading
import time

from aip.ui.modules.financial_analysis.viewmodels.financial_analysis_view_model import (
    FinancialAnalysisViewModel,
)
from aip.ui.modules.financial_analysis.views.financial_analysis_view import (
    FinancialAnalysisView,
)


class _Presenter:
    def __init__(self) -> None:
        self.worker_thread_ids: list[int] = []

    def build_view_model(self, **_kwargs: object) -> FinancialAnalysisViewModel:
        self.worker_thread_ids.append(threading.get_ident())
        return FinancialAnalysisViewModel()


def test_financial_workspace_loads_without_a_persistent_qthread(qt_app) -> None:
    presenter = _Presenter()
    main_thread_id = threading.get_ident()
    view = FinancialAnalysisView(presenter=presenter)  # type: ignore[arg-type]
    try:
        assert not hasattr(view, "_load_thread")
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            qt_app.processEvents()
            if presenter.worker_thread_ids and not view._loading:
                break
            time.sleep(0.01)

        assert presenter.worker_thread_ids
        assert all(worker_id != main_thread_id for worker_id in presenter.worker_thread_ids)
        assert isinstance(view.view_model(), FinancialAnalysisViewModel)
    finally:
        view.close()
        qt_app.processEvents()
