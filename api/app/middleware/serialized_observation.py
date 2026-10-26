"""Keep an admitted compatibility observation owned through request cancellation."""
from __future__ import annotations

import asyncio
import logging

import anyio

log = logging.getLogger(__name__)


class SerializedObservation:
    """One admitted operation; waiting requests remain cancellable.

    The operation owns its admission until the worker finishes. Shielding its
    task also covers raw ASGI Task.cancel(), which can otherwise release an
    AnyIO worker limiter while the synchronous function is still running.
    """

    def __init__(self):
        self._limiter = anyio.CapacityLimiter(1)
        self._pending: set[asyncio.Task] = set()

    async def run(self, function, *args):
        token = object()
        await self._limiter.acquire_on_behalf_of(token)
        task = asyncio.create_task(self._run_admitted(token, function, args))
        self._pending.add(task)
        task.add_done_callback(self._finished)
        return await asyncio.shield(task)

    async def _run_admitted(self, token, function, args):
        try:
            return await anyio.to_thread.run_sync(function, *args)
        finally:
            self._limiter.release_on_behalf_of(token)

    async def drain(self):
        """Graceful shutdown awaits admitted work; process termination is host-owned."""
        while self._pending:
            await asyncio.gather(*(asyncio.shield(task) for task in tuple(self._pending)), return_exceptions=True)

    def _finished(self, task):
        self._pending.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            log.warning("Admitted observation failed", exc_info=(type(error), error, error.__traceback__))
