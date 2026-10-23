"""Unit tests for the response cache, especially the empty-response rules."""

from __future__ import annotations

import pytest

from meta_reseek.search.base import SearchHit
from meta_reseek.search.cache import CachedProvider, FileCache


class CountingProvider:
    name = "count"

    def __init__(self, hits):
        self.hits = hits
        self.calls = 0
        self.last_error = None

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.calls += 1
        return self.hits


class FailingProvider(CountingProvider):
    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        super().search(query, max_results)
        self.last_error = "RequestError: tls handshake eof"
        return []


HIT = SearchHit("t", "https://a.example.com/x", "s")


def test_auto_mode_serves_cached_results(tmp_path):
    cache = FileCache(tmp_path)
    inner = CountingProvider([HIT])
    p = CachedProvider(inner, cache, mode="auto")
    p.search("q", 5)
    assert inner.calls == 1
    again = CachedProvider(CountingProvider([HIT]), cache, mode="auto")
    assert again.search("q", 5) == [HIT]
    assert again.network_calls == 0


def test_cached_empty_is_a_miss_in_auto_but_kept_for_offline(tmp_path):
    cache = FileCache(tmp_path)
    inner = CountingProvider([])  # transient backend failure
    CachedProvider(inner, cache, mode="auto").search("q", 5)

    # auto: cached empty -> retry live
    inner2 = CountingProvider([HIT])
    p_auto = CachedProvider(inner2, cache, mode="auto")
    assert p_auto.search("q", 5) == [HIT]
    assert p_auto.network_calls == 1

    # now the cache holds a non-empty response; offline replay sees it
    p_off = CachedProvider(CountingProvider([]), cache, mode="offline")
    assert p_off.search("q", 5) == [HIT]
    assert p_off.network_calls == 0


def test_offline_empty_round_is_reproduced(tmp_path):
    cache = FileCache(tmp_path)
    inner = CountingProvider([])  # a run that really got nothing
    CachedProvider(inner, cache, mode="refresh").search("q", 5)
    p = CachedProvider(CountingProvider([HIT]), cache, mode="offline")
    assert p.search("q", 5) == []  # replay shows the empty round as it happened
    assert p.network_calls == 0


def test_offline_cache_miss_raises(tmp_path):
    p = CachedProvider(CountingProvider([HIT]), FileCache(tmp_path), mode="offline")
    with pytest.raises(RuntimeError, match="offline"):
        p.search("missing", 5)


def test_refresh_mode_overwrites(tmp_path):
    cache = FileCache(tmp_path)
    CachedProvider(CountingProvider([HIT]), cache, mode="auto").search("q", 5)
    other = SearchHit("t2", "https://b.example.com/y", "s2")
    p = CachedProvider(CountingProvider([other]), cache, mode="refresh")
    assert p.search("q", 5) == [other]


def test_error_flag_is_persisted_and_replayed(tmp_path):
    cache = FileCache(tmp_path)
    live = CachedProvider(FailingProvider([]), cache, mode="auto")
    live.search("q", 5)
    assert live.last_error  # the live call failed

    replay = CachedProvider(CountingProvider([HIT]), cache, mode="offline")
    assert replay.search("q", 5) == []
    assert replay.last_error == "transport error (cached)"
    assert replay.network_calls == 0
