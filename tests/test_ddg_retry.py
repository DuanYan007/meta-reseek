"""Retry-state semantics of DdgProvider (no network).

The rule under test: a round that recovered after retries is a SUCCESS
(``last_error`` cleared, retries counted); only exhaustion of every attempt
counts as a final failure. This is what keeps provider_error in the
metacognitive feedback honest.
"""

from __future__ import annotations

import pytest

from meta_reseek.search.base import SearchHit
from meta_reseek.search.cache import CachedProvider, FileCache
from meta_reseek.search.ddg import DdgProvider

HIT = SearchHit("t", "https://a.example.com/x", "s")


class ScriptedDdg(DdgProvider):
    """_fetch raises the given exceptions in order, then returns HITs."""

    def __init__(self, failures: list[Exception]):
        super().__init__()
        self.failures = list(failures)
        self.calls = 0

    def _fetch(self, query: str, max_results: int) -> list[SearchHit]:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return [HIT]


def _provider(failures):
    p = ScriptedDdg(failures)
    p.retry_sleep = 0
    return p


def test_success_after_retry_clears_error_state():
    p = _provider([RuntimeError("boom"), RuntimeError("boom")])
    hits = p.search("q", 5)
    assert hits == [HIT]                       # recovered
    assert p.last_error is None                # NOT an error round anymore
    assert p.last_retries == 2                 # but the recovery is visible
    assert p.calls == 3


def test_all_attempts_failed_is_final_error():
    p = _provider([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    assert p.search("q", 5) == []
    assert p.last_error is not None
    assert "RuntimeError" in p.last_error
    assert p.calls == 3


def test_clean_success_has_no_error_and_no_retries():
    p = _provider([])
    assert p.search("q", 5) == [HIT]
    assert p.last_error is None
    assert p.last_retries == 0
    assert p.calls == 1


def test_cached_recovery_replays_without_error(tmp_path):
    cache = FileCache(tmp_path)
    live = CachedProvider(_provider([RuntimeError("boom")]), cache, mode="refresh")
    assert live.search("q", 5) == [HIT]
    assert live.last_error is None and live.last_retries == 1

    replay = CachedProvider(_provider([]), cache, mode="offline")
    assert replay.search("q", 5) == [HIT]
    assert replay.last_error is None          # recovery replays as success
    assert replay.last_retries == 1           # retry count reproduced
    assert replay.network_calls == 0


def test_cached_final_failure_replays_as_error(tmp_path):
    cache = FileCache(tmp_path)
    fails = [RuntimeError("x"), RuntimeError("y"), RuntimeError("z")]
    CachedProvider(_provider(fails), cache, mode="refresh").search("q", 5)

    replay = CachedProvider(_provider([]), cache, mode="offline")
    assert replay.search("q", 5) == []
    assert replay.last_error == "transport error (cached)"
    assert replay.network_calls == 0


def test_controller_sees_recovered_round_as_success():
    """End-to-end: a retry-recovered search round must not be flagged
    provider_error, but the retry count must be recorded."""
    from meta_reseek.metacog.controller import MetacognitiveController

    from conftest import MockProvider, WINNERS_HITS, make_task

    class RecoveringProvider(MockProvider):
        name = "ddg"

        def __init__(self):
            super().__init__([("*", WINNERS_HITS)])
            self.last_error = None
            self.last_retries = 1  # simulate: recovered after one retry

    task = make_task(max_rounds=4)
    log = MetacognitiveController(task, RecoveringProvider()).run()
    r1 = log.records[0]
    assert r1.decision == "search"
    assert r1.ingest["added"] > 0            # results actually arrived
    assert r1.feedback["provider_error"] is False   # NOT marked as failure
    assert r1.feedback["provider_retries"] == 1     # recovery still visible


@pytest.mark.parametrize("failures,expect_error,expect_retries", [
    ([], False, 0),
    ([RuntimeError("one")], False, 1),
    ([RuntimeError("one"), RuntimeError("two"), RuntimeError("three")], True, 0),
])
def test_retry_outcome_matrix(failures, expect_error, expect_retries):
    p = _provider(failures)
    p.search("q", 5)
    assert (p.last_error is not None) == expect_error
    assert p.last_retries == expect_retries
