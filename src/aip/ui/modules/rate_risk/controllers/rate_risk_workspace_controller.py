from __future__ import annotations

from datetime import date

from aip.application.irrbb import IRRBBAnalysisRequestProvider, RunIRRBBAnalysis
from aip.ui.modules.rate_risk.models import RateRiskReadModel
from aip.ui.modules.rate_risk.presenters import RateRiskPresenter


class RateRiskWorkspaceController:
    """Coordinate RTILB application execution and passive UI presentation.

    The controller contains no financial methodology. It obtains the approved
    request from an injected provider, executes the application use case and maps
    the resulting application contract into the immutable UI read model.
    """

    def __init__(
        self,
        *,
        analysis: RunIRRBBAnalysis,
        request_provider: IRRBBAnalysisRequestProvider,
    ) -> None:
        self._analysis = analysis
        self._request_provider = request_provider

    def load(self, *, cutoff_date: date) -> RateRiskReadModel:
        request = self._request_provider.request_for(cutoff_date=cutoff_date)
        if request.cutoff_date != cutoff_date:
            raise ValueError(
                "IRRBB request provider returned a request for a different cutoff date"
            )
        result = self._analysis.execute(request)
        return RateRiskPresenter.build_from_analysis(request=request, result=result)
