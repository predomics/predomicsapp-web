"""Simple in-memory TTL cache for expensive endpoint responses."""

import hashlib
import json
import time
from functools import wraps
from typing import Any

_cache: dict[str, tuple[Any, float]] = {}


def cache_key(*args, **kwargs) -> str:
    raw = json.dumps({"a": args, "k": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl_seconds: int = 300):
    """Decorator: cache async function result for ttl_seconds."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            now = time.time()
            if key in _cache:
                val, expires = _cache[key]
                if now < expires:
                    return val
            result = await func(*args, **kwargs)
            _cache[key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return decorator


def invalidate(prefix: str = ""):
    """Invalidate cache entries matching prefix."""
    keys_to_remove = [k for k in _cache if k.startswith(prefix)]
    for k in keys_to_remove:
        del _cache[k]
