import pytest

from aip.core.exceptions import ValidationError
from aip.core.identifiers import EntityId


def test_new_entity_id_is_valid() -> None:
    identifier = EntityId.new()
    assert EntityId.from_string(str(identifier)) == identifier


def test_invalid_entity_id_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as captured:
        EntityId.from_string("not-a-uuid")
    assert captured.value.code == "INVALID_ENTITY_ID"
