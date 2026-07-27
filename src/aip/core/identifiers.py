from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from aip.core.exceptions import ValidationError
from aip.core.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class EntityId(ValueObject):
    """Identificador UUID fuertemente tipado para entidades del dominio."""

    value: UUID

    @classmethod
    def new(cls) -> "EntityId":
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> "EntityId":
        try:
            return cls(UUID(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValidationError(
                "El identificador no contiene un UUID válido.",
                code="INVALID_ENTITY_ID",
                details={"value": value},
            ) from exc

    def validate(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValidationError(
                "EntityId requiere una instancia UUID.",
                code="INVALID_ENTITY_ID_TYPE",
                details={"type": type(self.value).__name__},
            )

    def __str__(self) -> str:
        return str(self.value)
