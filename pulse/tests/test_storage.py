"""Storage layer tests — fresh DB per test, no fixtures beyond tmp_path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pulse_app.storage import Sample, Store, iso_utc


def _mk_sample(
    organ: str, ok: bool, minutes_ago: int, latency_ms: int = 42
) -> Sample:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return Sample(
        ts=iso_utc(dt),
        organ=organ,
        ok=ok,
        latency_ms=latency_ms,
        detail=None if ok else "synthetic failure",
    )


def test_schema_created_on_first_open(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    # Smoke: count_samples succeeds on an empty fresh DB.
    assert store.count_samples() == 0


def test_insert_and_count(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    store.insert_sample(_mk_sample("api", True, 1))
    store.insert_sample(_mk_sample("api", False, 0))
    assert store.count_samples() == 2


def test_insert_samples_batch(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    batch = [
        _mk_sample("api", True, 3),
        _mk_sample("web", True, 3),
        _mk_sample("postgres", False, 3),
    ]
    store.insert_samples(batch)
    assert store.count_samples() == 3


def test_last_sample_for_organ(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    store.insert_sample(_mk_sample("api", True, 5))
    store.insert_sample(_mk_sample("api", False, 1))  # more recent
    store.insert_sample(_mk_sample("web", True, 2))

    last_api = store.last_sample_for_organ("api")
    assert last_api is not None
    assert last_api.ok is False
    assert last_api.organ == "api"

    last_web = store.last_sample_for_organ("web")
    assert last_web is not None
    assert last_web.ok is True


def test_last_sample_none_when_missing(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    assert store.last_sample_for_organ("ghost") is None


def test_recent_samples_chronological(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    for m in (10, 8, 6, 4, 2):
        store.insert_sample(_mk_sample("api", True, m))
    recent = store.recent_samples_for_organ("api", limit=3)
    assert len(recent) == 3
    # Chronological (oldest first) — so later indices are more recent.
    assert recent[0].ts < recent[1].ts < recent[2].ts


def test_samples_since_window(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    for m in (120, 60, 30, 5):  # minutes ago
        store.insert_sample(_mk_sample("api", True, m))
    since = iso_utc(datetime.now(timezone.utc) - timedelta(minutes=45))
    got = store.samples_for_organ_since("api", since)
    assert len(got) == 2  # the 30-min and 5-min ones


def test_silence_open_close_roundtrip(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    started = iso_utc()
    sid = store.open_silence("api", started, "strained")
    assert sid > 0

    # Ongoing read
    ongoing = store.ongoing_silence_for_organ("api")
    assert ongoing is not None and ongoing.id == sid and ongoing.ended_at is None

    # Escalate
    store.escalate_silence(sid, "silent")
    ongoing2 = store.ongoing_silence_for_organ("api")
    assert ongoing2 is not None and ongoing2.severity == "silent"

    # Close
    store.close_silence(sid, iso_utc())
    assert store.ongoing_silence_for_organ("api") is None


def test_delete_samples_older_than(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    store.insert_sample(_mk_sample("api", True, 60 * 24 * 200))  # ~200d ago
    store.insert_sample(_mk_sample("api", True, 60 * 24 * 10))   # ~10d ago
    cutoff = iso_utc(datetime.now(timezone.utc) - timedelta(days=100))
    deleted = store.delete_samples_older_than(cutoff)
    assert deleted == 1
    assert store.count_samples() == 1
