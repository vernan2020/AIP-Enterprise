from __future__ import annotations

from decimal import Decimal

from aip.product.configured.irrbb.regulatory_gap_six_band import (
    REGULATORY_BRECHA_BUCKETS,
    RegulatoryGapBucket,
    RegulatoryGapResult,
)
from aip.ui.modules.rate_risk.views.regulatory_gap_chart import RegulatoryGapChart


def test_regulatory_gap_chart_uses_only_reconciled_six_band_source(qt_app) -> None:
    chart = RegulatoryGapChart()
    try:
        chart.resize(950, 280)
        chart.set_result(RegulatoryGapResult("BLOCKED", issues=("Cuenta faltante.",)))
        assert chart._rows == ()
        assert "Sin GAP conciliado" in chart.accessibleDescription()
        blocked = chart.grab()
        assert blocked.width() > 0

        rows = tuple(
            RegulatoryGapBucket(
                bucket_code=code,
                bucket_label=label,
                assets_crc=Decimal("100.00"),
                liabilities_crc=Decimal("70.00"),
                gap_crc=Decimal("30.00") if i % 2 == 0 else Decimal("-30.00"),
                cumulative_gap_crc=Decimal("30.00") if i % 2 == 0 else Decimal("0.00"),
            )
            for i, (code, label) in enumerate(REGULATORY_BRECHA_BUCKETS)
        )
        chart.set_result(RegulatoryGapResult("RECONCILED", rows=rows))
        assert len(chart._rows) == 6
        assert chart.accessibleName() == "GAP regulatorio por banda SICVECA"
        assert "conciliado" in chart.accessibleDescription()
        rendered = chart.grab()
        assert rendered.size() == blocked.size()

        chart.set_result(RegulatoryGapResult("BLOCKED", issues=("Corte incorrecto.",)))
        assert chart._rows == ()
    finally:
        chart.close()
