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


def test_cache_size_counts_only_live_entries() -> None:
    cache = BCCRCache(ttl_seconds=300)

    cache.set("TPM", {"value": 3.25}, ttl_seconds=900)
    cache.set("EXPIRED", {"value": 0}, ttl_seconds=0)

    assert cache.size() == 1
    assert cache.get("TPM") == {"value": 3.25}
    assert cache.get("EXPIRED") is None
