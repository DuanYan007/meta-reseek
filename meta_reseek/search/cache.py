"""On-disk response cache: makes real-search runs replayable offline.

Cache key = hash(provider, query, max_results). The cached JSON stores the
fetch timestamp, so a replayed trace can honestly say which round hit the
network and which was served from cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .base import SearchHit, SearchProvider


class FileCache:
    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.base / f"{key}.json"

    @staticmethod
    def key(provider: str, query: str, max_results: int) -> str:
        raw = f"{provider}|{query.strip().lower()}|{max_results}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> list[SearchHit] | None:
        """Cached hits, or None on a miss. A cached *empty* response is
        returned as an empty list (it happened; replays must see it)."""
        path = self._path(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return [SearchHit(**h) for h in data["hits"]]

    def get_meta(self, key: str) -> dict | None:
        """Cache entry metadata (e.g. whether the live call had erred)."""
        path = self._path(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"error": bool(data.get("error", False)), "fetched_at": data.get("fetched_at")}

    def put(self, key: str, hits: list[SearchHit], error: bool = False) -> None:
        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error": error,
            "hits": [asdict(h) for h in hits],
        }
        self._path(key).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )


class CachedProvider:
    """Wraps a provider with FileCache behaviour.

    mode:
      - "auto": serve from cache when present, otherwise hit the network;
      - "refresh": always hit the network and overwrite the cache;
      - "offline": never hit the network; a cache miss is an error
        (reproducible replay of an earlier real run).
    """

    def __init__(self, inner: SearchProvider, cache: FileCache, mode: str = "auto"):
        if mode not in {"auto", "refresh", "offline"}:
            raise ValueError(f"unknown cache mode: {mode}")
        self.inner = inner
        self.cache = cache
        self.mode = mode
        self.name = inner.name
        self.network_calls = 0
        self.last_error: str | None = None  # error state of the LAST search call

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        key = FileCache.key(self.inner.name, query, max_results)
        if self.mode != "refresh":
            hits = self.cache.get(key)
            if hits is not None:
                if hits or self.mode == "offline":
                    # replay the recorded round exactly, error flag included:
                    # an offline rerun must attribute failures the same way
                    meta = self.cache.get_meta(key) or {}
                    self.last_error = (
                        "transport error (cached)" if meta.get("error") else None
                    )
                    return hits
                # auto mode + cached empty: likely a transient backend
                # failure worth retrying live
        if self.mode == "offline":
            raise RuntimeError(
                f"offline mode: no cached result for query {query!r}; "
                "run once with --cache auto or refresh first"
            )
        self.network_calls += 1
        hits = self.inner.search(query, max_results)
        self.last_error = getattr(self.inner, "last_error", None)
        # Empty responses and errors are cached too (they are part of what
        # really happened), but auto mode treats cached empties as a miss.
        self.cache.put(key, hits, error=bool(self.last_error))
        return hits
