from aip.core.exceptions import ValidationError


def test_aip_error_exposes_structured_context() -> None:
    error = ValidationError("Dato inválido.", code="TEST_VALIDATION", details={"field": "amount"})
    assert error.code == "TEST_VALIDATION"
    assert error.details["field"] == "amount"
    assert str(error) == "[TEST_VALIDATION] Dato inválido."
