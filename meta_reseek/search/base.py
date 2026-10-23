"""Search provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str


@runtime_checkable
class SearchProvider(Protocol):
    """A real (or mocked, for tests) external search backend."""

    name: str

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        ...
