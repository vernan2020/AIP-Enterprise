from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass


class ImmutableIndicatorCodes(tuple):
    """Tuple-like container that raises when mutation is attempted."""

    def append(self, value: str) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")

    def extend(self, values: object) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")

    def insert(self, index: int, value: str) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")

    def remove(self, value: str) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")

    def pop(self, index: int = -1) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")

    def clear(self) -> None:  # noqa: ANN401
        raise FrozenInstanceError("cannot mutate indicator_codes")


@dataclass(frozen=True, slots=True)
class BCCRRequest:
    """Request describing the BCCR indicator series to fetch."""

    indicator_codes: tuple[str, ...] | list[str]
    from_date: str
    to_date: str
    format: str = "json"
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        normalized_codes = tuple(self.indicator_codes)
        object.__setattr__(self, "indicator_codes", ImmutableIndicatorCodes(normalized_codes))

    def to_dict(self) -> dict[str, object]:
        return {
            "indicator_codes": list(self.indicator_codes),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "format": self.format,
            "etag": self.etag,
            "last_modified": self.last_modified,
        }
