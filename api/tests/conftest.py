"""Pytest configuration and fixtures."""

pytest_plugins = ("pytest_asyncio",)


def _register_test_500_route():
    """Register GET /api/_test_500 to trigger 500 handler (spec 009 test)."""
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/_test_500")
    async def _test_500():
        raise RuntimeError("test")

    from app.main import app
    app.include_router(router, prefix="/api", tags=["_test"])


_register_test_500_route()
