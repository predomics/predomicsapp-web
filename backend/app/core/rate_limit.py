"""Rate limiting setup using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings


def _get_user_or_ip(request):
    """Rate limit key: user ID from JWT if available, else IP address."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        from .security import decode_access_token

        user_id = decode_access_token(auth[7:])
        if user_id:
            return user_id
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return f"apikey:{api_key[:8]}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_user_or_ip,
    default_limits=[settings.rate_limit_api] if settings.rate_limit_enabled else [],
    enabled=settings.rate_limit_enabled,
)
