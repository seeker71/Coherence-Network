"""Provider usage adapters, normalized snapshots, and alert evaluation.

This package splits the former single-file automation_usage_service into
smaller modules. The public API and test-used internals are re-exported
here and from app.services.automation_usage_service for backward compatibility.
"""

from __future__ import annotations

# Re-export public API and symbols used by tests (monkeypatch targets).
# Submodules are loaded lazily via the facade to avoid circular imports.
__all__: list[str] = []
