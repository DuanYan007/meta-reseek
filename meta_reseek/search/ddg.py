"""DuckDuckGo web search via the ``ddgs`` package (no API key required).

The backend occasionally answers transient errors / rate limits with
"No results found". A failed call is retried a couple of times and finally
reported as an empty result page (zero gain for that round) instead of
killing the whole metacognitive run; errors are recorded on ``self.errors``
and surfaced in the run trace.
"""

from __future__ import annotations

import time

from ddgs import DDGS

from .base import SearchHit

_RETRIES = 2
_RETRY_SLEEP = 1.5


class DdgProvider:
    name = "ddg"

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.last_error: str | None = None  # error state of the LAST search call

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.last_error = None
        for attempt in range(_RETRIES + 1):
            try:
                hits: list[SearchHit] = []
                with DDGS() as ddgs:
                    for raw in ddgs.text(query, max_results=max_results):
                        # ddgs result keys have shifted across versions; read defensively.
                        hits.append(
                            SearchHit(
                                title=str(raw.get("title", "") or ""),
                                url=str(raw.get("href", raw.get("url", "")) or ""),
                                snippet=str(
                                    raw.get(
                                        "body",
                                        raw.get("description", raw.get("snippet", "")),
                                    )
                                    or ""
                                ),
                            )
                        )
                return hits
            except Exception as exc:  # noqa: BLE001 - degrade, never kill the run
                self.errors.append(f"round-query {query!r} attempt {attempt}: {exc}")
                self.last_error = f"{type(exc).__name__}: {exc}"
                if attempt < _RETRIES:
                    time.sleep(_RETRY_SLEEP)
        return []
