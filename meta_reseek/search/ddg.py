"""DuckDuckGo web search via the ``ddgs`` package (no API key required).

The backend occasionally answers transient errors / rate limits with
"No results found". A failed attempt is retried a couple of times:

- ``last_error``   is set ONLY when every attempt failed (the round's final
                    outcome is a failure; feedback marks it provider_error);
- ``last_retries`` counts failed attempts before a SUCCESSFUL fetch. A round
                    that recovered after retries is a success, not an error,
                    but the recovery itself stays visible in the trace.

Attempt-level details are appended to ``self.errors`` for debugging and are
surfaced in the run trace config.
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
        self.last_error: str | None = None   # final failure of the LAST call
        self.last_retries: int = 0           # failed attempts before success
        self.retry_sleep: float = _RETRY_SLEEP

    def _fetch(self, query: str, max_results: int) -> list[SearchHit]:
        """One backend call. Split out so tests can script failures."""
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
                                "body", raw.get("description", raw.get("snippet", ""))
                            )
                            or ""
                        ),
                    )
                )
        return hits

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.last_error = None
        self.last_retries = 0
        for attempt in range(_RETRIES + 1):
            try:
                hits = self._fetch(query, max_results)
            except Exception as exc:  # noqa: BLE001 - degrade, never kill the run
                self.errors.append(f"query {query!r} attempt {attempt}: {exc}")
                if attempt < _RETRIES:
                    time.sleep(self.retry_sleep)
                    continue
                self.last_error = f"{type(exc).__name__}: {exc}"
                return []
            # success — even if earlier attempts failed, this round's outcome
            # is a success; only the retry count remembers the recovery
            self.last_retries = attempt
            return hits
        return []  # unreachable; keeps type-checkers content
