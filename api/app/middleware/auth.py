"""API authentication middleware.

Three auth levels:
- PUBLIC: no auth needed (GET endpoints, health)
- API_KEY: requires X-API-Key header (mutating endpoints)
- ADMIN: requires X-Admin-Key header (destructive operations)

Keys configured in api/config/api.json under auth.api_key and auth.admin_key.
"""

import os
from fastapi import Header, HTTPException, Depends

from app.services.config_service import get_api_key, is_production

try:
    from app.config_loader import api_config
    _API_KEY = api_config("auth", "api_key", "dev-key") or get_api_key()
    _ADMIN_KEY = api_config("auth", "admin_key", "dev-admin") or "dev-admin"
except ImportError:
    _API_KEY = get_api_key()
    _ADMIN_KEY = os.environ.get("COHERENCE_ADMIN_KEY", "") or "dev-admin"
_PRODUCTION = is_production()

# Fail-fast: refuse to start in production with default keys
if _PRODUCTION and _API_KEY == "dev-key":
    raise RuntimeError("COHERENCE_API_KEY must be set for production (not 'dev-key')")
if _PRODUCTION and _ADMIN_KEY == "dev-admin":
    raise RuntimeError("COHERENCE_ADMIN_KEY must be set for production (not 'dev-admin')")


def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    """Dependency for API_KEY level auth."""
    if _PRODUCTION and _API_KEY == "dev-key":
        raise HTTPException(500, "API key not configured for production")
    if not x_api_key or x_api_key != _API_KEY:
        raise HTTPException(401, "Invalid or missing X-API-Key header")
    return x_api_key


def require_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")) -> str:
    """Dependency for ADMIN level auth."""
    if _PRODUCTION and _ADMIN_KEY == "dev-admin":
        raise HTTPException(500, "Admin key not configured for production")
    if not x_admin_key or x_admin_key != _ADMIN_KEY:
        raise HTTPException(401, "Invalid or missing X-Admin-Key header")
    return x_admin_key
