from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Attachment:
    """Immutable report attachment."""

    name: str
    content_type: str = "application/octet-stream"
    data: bytes | None = None
    uri: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata))
