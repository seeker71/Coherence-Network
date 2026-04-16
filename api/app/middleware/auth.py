"""API authentication middleware.

Three auth levels:
- PUBLIC: no auth needed (GET endpoints, health)
- API_KEY: requires X-API-Key header (mutating endpoints)
- ADMIN: requires X-Admin-Key header (destructive operations)

Keys resolve via `config_loader.auth_api_key()` /
`config_loader.auth_admin_key()`, which honor `AUTH_API_KEY` /
`AUTH_ADMIN_KEY` env vars (12-factor) before falling back to
api/config/api.json.
"""

from fastapi import Header, HTTPException

from app.config_loader import auth_admin_key, auth_api_key
from app.services.config_service import is_production

def _current_api_key() -> str:
    if _API_KEY is not None:
        return _API_KEY
    return auth_api_key()


def _current_admin_key() -> str:
    if _ADMIN_KEY is not None:
        return _ADMIN_KEY
    return auth_admin_key()


def _in_production() -> bool:
    if _PRODUCTION is not None:
        return bool(_PRODUCTION)
    return is_production()


_API_KEY: str | None = None
_ADMIN_KEY: str | None = None
_PRODUCTION: bool | None = None

# Fail-fast: refuse to start in production with default keys
if _in_production() and _current_api_key() == "dev-key":
    raise RuntimeError("API auth.api_key must be set for production (not 'dev-key')")
if _in_production() and _current_admin_key() == "dev-admin":
    raise RuntimeError("API auth.admin_key must be set for production (not 'dev-admin')")


def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    """Dependency for API_KEY level auth."""
    api_key = _current_api_key()
    if _in_production() and api_key == "dev-key":
        raise HTTPException(500, "API key not configured for production")
    if not x_api_key or x_api_key != api_key:
        raise HTTPException(401, "Invalid or missing X-API-Key header")
    return x_api_key


def require_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")) -> str:
    """Dependency for ADMIN level auth."""
    admin_key = _current_admin_key()
    if _in_production() and admin_key == "dev-admin":
        raise HTTPException(500, "Admin key not configured for production")
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(401, "Invalid or missing X-Admin-Key header")
    return x_admin_key
