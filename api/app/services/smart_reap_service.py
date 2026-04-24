"""Compatibility shim for the canonical smart reaper service.

The implementation lives in ``app.services.smart_reaper_service``. This module
keeps older imports working while avoiding a second copy of the same organ.
"""

from __future__ import annotations

from app.services.smart_reaper_service import *  # noqa: F401,F403
