"""Scheduled probe runner.

APScheduler runs `probe_round` every PULSE_INTERVAL_SECONDS. Each round
fans out probes, records samples, and reconciles silences for every organ.

A separate daily job trims samples older than PULSE_RETENTION_DAYS.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pulse_app.analysis import reconcile_silences
from pulse_app.organs import ORGANS
from pulse_app.probe import probe_all
from pulse_app.storage import Store, iso_utc


logger = logging.getLogger("pulse.scheduler")


@dataclass(frozen=True)
class SchedulerConfig:
    api_base: str
    web_base: str
    interval_seconds: int = 30
    retention_days: int = 180


class PulseScheduler:
    def __init__(self, store: Store, config: SchedulerConfig) -> None:
        self.store = store
        self.config = config
        self._scheduler: AsyncIOScheduler | None = None

    async def probe_round(self) -> None:
        try:
            samples = await probe_all(self.config.api_base, self.config.web_base)
            self.store.insert_samples(samples)
            for organ in ORGANS:
                try:
                    reconcile_silences(self.store, organ.name)
                except Exception:
                    logger.exception(
                        "silence reconciliation failed organ=%s", organ.name
                    )
            logger.info(
                "probe_round ok samples=%d healthy=%d",
                len(samples),
                sum(1 for s in samples if s.ok),
            )
        except Exception:
            logger.exception("probe_round crashed")

    async def vacuum_round(self) -> None:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(
                days=self.config.retention_days
            )
            deleted = self.store.delete_samples_older_than(iso_utc(cutoff))
            if deleted:
                logger.info("vacuum removed %d old samples", deleted)
        except Exception:
            logger.exception("vacuum_round crashed")

    def start(self) -> None:
        if self._scheduler is not None:
            return
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            self.probe_round,
            trigger=IntervalTrigger(seconds=self.config.interval_seconds),
            id="probe_round",
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(timezone.utc),
        )
        scheduler.add_job(
            self.vacuum_round,
            trigger=IntervalTrigger(hours=24),
            id="vacuum_round",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        self._scheduler = scheduler
        logger.info(
            "pulse scheduler started interval=%ds retention=%dd",
            self.config.interval_seconds,
            self.config.retention_days,
        )

    def shutdown(self) -> None:
        if self._scheduler is None:
            return
        self._scheduler.shutdown(wait=False)
        self._scheduler = None
        logger.info("pulse scheduler stopped")
