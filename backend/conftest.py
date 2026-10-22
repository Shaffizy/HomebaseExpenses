import pytest


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Rate-limit keys must not leak between tests (locmem cache is in-process)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
