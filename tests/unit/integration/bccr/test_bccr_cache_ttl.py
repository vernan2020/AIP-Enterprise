from __future__ import annotations

from aip.integration.bccr.connector.cache import BCCRCache


def test_cache_accepts_per_entry_ttl() -> None:
    cache = BCCRCache(ttl_seconds=300)

    cache.set("TPM", {"value": 3.25}, ttl_seconds=900)

    assert cache.get("TPM") == {"value": 3.25}


def test_cache_uses_entry_ttl_for_expiration() -> None:
    cache = BCCRCache(ttl_seconds=300)

    cache.set("TPM", {"value": 3.25}, ttl_seconds=0)

    assert cache.get("TPM") is None
