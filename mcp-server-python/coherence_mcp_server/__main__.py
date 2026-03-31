"""Entry point for coherence-mcp-server Python package.

Run via:
    python -m coherence_mcp_server
    coherence-mcp-server        (after pip install)
    uvx coherence-mcp-server    (via uv)
"""

import asyncio
import sys


def main() -> None:
    """Start the Coherence Network MCP server."""
    from coherence_mcp_server.server import run
    asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
