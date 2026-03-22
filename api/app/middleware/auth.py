"""API authentication middleware.

Three auth levels:
- PUBLIC: no auth needed (GET endpoints, health)
- API_KEY: requires X-API-Key header (mutating endpoints)
- ADMIN: requires X-Admin-Key header (destructive operations)

Keys are configured via environment variables:
- COHERENCE_API_KEY: for API_KEY level (default: "dev-key" in dev, required in production)
- COHERENCE_ADMIN_KEY: for ADMIN level (default: "dev-admin" in dev, required in production)
"""

import os
from fastapi import Header, HTTPException, Depends

from app.services import config_service

_API_KEY = config_service.get_key("coherence", "api_key") or os.environ.get("COHERENCE_API_KEY", "dev-key")
_ADMIN_KEY = config_service.get_key("coherence", "admin_key") or os.environ.get("COHERENCE_ADMIN_KEY", "dev-admin")
_PRODUCTION = config_service.is_production()

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
