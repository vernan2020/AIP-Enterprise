from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuoteUpdated:
    """Domain event emitted when a quote is updated."""

    quote_id: str
