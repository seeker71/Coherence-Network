"""File-configured production ASGI carrier."""

from __future__ import annotations

import uvicorn

from app.config_loader import get_list


def main() -> None:
    """Launch Uvicorn from the shared file-backed configuration surface."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        ws="websockets-sansio",
        proxy_headers=True,
        forwarded_allow_ips=get_list(
            "server",
            "forwarded_allow_ips",
            ["127.0.0.1", "172.16.0.0/12"],
        ),
    )


if __name__ == "__main__":
    main()
