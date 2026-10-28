from aip.product.economic.economic_viewmodel import EconomicViewModel


def test_macro_fallback_tuple_diagnostics_remain_visible() -> None:
    payload = {
        "diagnostics": ("Live BCCR unavailable: FX: HTTP 500", "TPM: HTTP 500"),
        "status": "AVAILABLE",
    }
    assert EconomicViewModel._build_diagnostics(payload) == (
        "Live BCCR unavailable: FX: HTTP 500",
        "TPM: HTTP 500",
    )
