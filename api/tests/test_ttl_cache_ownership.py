"""Expensive reads publish fresh results and share an owned computation."""
import threading
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from app.core import ttl_cache


@pytest.fixture(autouse=True)
def cache_enabled(monkeypatch):
    monkeypatch.setattr(ttl_cache, "_is_disabled", lambda: False)


def _observe_waiter(monkeypatch):
    waiting = threading.Event()
    class ObservedFuture(Future):
        def result(self, timeout=None):
            waiting.set()
            return super().result(timeout=timeout)
    monkeypatch.setattr(ttl_cache, "Future", ObservedFuture)
    return waiting


def test_ttl_starts_when_computation_finishes(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(ttl_cache.time, "monotonic", lambda: clock[0])
    calls = []
    @ttl_cache.ttl_cached(ttl_seconds=30)
    def build():
        calls.append(1)
        clock[0] += 120
        return len(calls)
    assert build() == 1
    assert build() == 1
    assert len(calls) == 1
    clock[0] += 31
    assert build() == 2


def test_same_key_shares_work_while_other_keys_can_finish(monkeypatch):
    waiting = _observe_waiter(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    calls = []
    @ttl_cache.ttl_cached()
    def build(key):
        calls.append(key)
        if key == "slow":
            entered.set()
            assert release.wait(3)
        return key
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(build, "slow")
        assert entered.wait(1)
        second = pool.submit(build, "slow")
        try:
            assert waiting.wait(1)
            assert pool.submit(build, "other").result(timeout=1) == "other"
            assert calls.count("slow") == 1
        finally:
            release.set()
        assert first.result(timeout=1) == second.result(timeout=1) == "slow"
    assert calls.count("slow") == 1


def test_old_completion_does_not_remove_live_replacement(monkeypatch):
    waiting = _observe_waiter(monkeypatch)
    entered = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    calls = []
    @ttl_cache.ttl_cached()
    def build():
        number = len(calls)
        calls.append(number)
        if number < 2:
            entered[number].set()
            assert release[number].wait(3)
        return number
    with ThreadPoolExecutor(max_workers=3) as pool:
        old = pool.submit(build)
        assert entered[0].wait(1)
        build.cache_clear()
        new = pool.submit(build)
        try:
            assert entered[1].wait(1)
            release[0].set()
            assert old.result(timeout=1) == 0
            follower = pool.submit(build)
            assert waiting.wait(1)
            assert calls == [0, 1]
        finally:
            release[0].set()
            release[1].set()
        assert new.result(timeout=1) == follower.result(timeout=1) == 1
    assert build() == 1


def test_waiters_receive_failure_and_a_later_call_retries(monkeypatch):
    waiting = _observe_waiter(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    calls = []
    class InterruptedRead(BaseException):
        pass
    @ttl_cache.ttl_cached()
    def build():
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
            raise InterruptedRead("synthetic interruption")
        return "complete"
    with ThreadPoolExecutor(max_workers=2) as pool:
        leader = pool.submit(build)
        assert entered.wait(1)
        follower = pool.submit(build)
        try:
            assert waiting.wait(1)
        finally:
            release.set()
        for result in (leader, follower):
            with pytest.raises(InterruptedRead, match="synthetic interruption"):
                result.result(timeout=1)
    assert build() == "complete"
    assert calls == [1, 1]


def test_clear_keeps_old_work_owned_without_republishing_it():
    entered, release = threading.Event(), threading.Event()
    calls = []
    @ttl_cache.ttl_cached()
    def build():
        number = len(calls) + 1
        calls.append(number)
        if number == 1:
            entered.set()
            assert release.wait(3)
        return number
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(build)
        assert entered.wait(1)
        try:
            build.cache_clear()
            assert build() == 2
        finally:
            release.set()
        assert old.result(timeout=1) == 1
    assert build() == 2


def test_failed_computation_releases_the_key_for_retry():
    calls = []
    @ttl_cache.ttl_cached()
    def build():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("synthetic computation failed")
        return "complete"
    with pytest.raises(ValueError, match="synthetic computation failed"):
        build()
    assert build() == "complete"
    assert build() == "complete"
    assert len(calls) == 2


def test_unhashable_input_uses_uncached_function():
    @ttl_cache.ttl_cached()
    def build(value):
        return value
    assert build(["play"]) == ["play"]
