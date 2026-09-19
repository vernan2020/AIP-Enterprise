from __future__ import annotations

import inspect

from aip.product.configured.irrbb.semantic_model_inspection_composition import (
    build_configured_semantic_model_inspection_coordinator,
)


def test_power_bi_composition_requires_explicit_token_provider() -> None:
    """Prevent accidental introduction of an implicit credential strategy."""

    parameter = inspect.signature(
        build_configured_semantic_model_inspection_coordinator
    ).parameters["token_provider"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
