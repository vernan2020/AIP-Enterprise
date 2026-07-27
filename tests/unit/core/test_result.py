import pytest

from aip.core.exceptions import ValidationError
from aip.core.result import Result


def test_success_exposes_value() -> None:
    result = Result.success(10)
    assert result.is_success
    assert not result.is_failure
    assert result.value == 10


def test_failure_raises_original_error_when_value_is_requested() -> None:
    error = ValidationError("Valor incorrecto.")
    result: Result[int] = Result.failure(error)
    with pytest.raises(ValidationError) as captured:
        _ = result.value
    assert captured.value is error


def test_map_transforms_success() -> None:
    assert Result.success(4).map(lambda value: value * 2).value == 8


def test_bind_preserves_failure() -> None:
    error = ValidationError("No procesable.")
    result: Result[int] = Result.failure(error)
    chained = result.bind(lambda value: Result.success(str(value)))
    assert chained.is_failure
    assert chained.error is error
