"""Shared fixtures: an offline task and a scripted mock provider."""

from __future__ import annotations

import pytest

from meta_reseek.search.base import SearchHit
from meta_reseek.task import SubQuestion, TaskSpec


def make_task(max_rounds: int = 6) -> TaskSpec:
    return TaskSpec(
        name="unit_task",
        question="Who won the 2024 Nobel Prize in Physics and for what work?",
        seed_query="2024 Nobel Prize in Physics",
        sub_questions=[
            SubQuestion(
                id="winners",
                text="Who are the laureates of the 2024 Nobel Prize in Physics",
                keywords=["Nobel Prize", "Physics", "2024", "laureates"],
                alt_queries=["2024 Nobel Physics winners names"],
            ),
            SubQuestion(
                id="work",
                text="What specific work was the 2024 Physics Nobel awarded for",
                keywords=["artificial neural networks", "machine learning"],
                alt_queries=["2024 Nobel Physics motivation neural networks"],
            ),
        ],
        min_relevant_per_subq=2,
        max_rounds=max_rounds,
    )


def hit(url: str, title: str, snippet: str) -> SearchHit:
    return SearchHit(title=title, url=url, snippet=snippet)


WINNERS_HITS = [
    hit(
        "https://en.wikipedia.org/wiki/2024_Nobel_Prize",
        "2024 Nobel Prizes in Physics - Wikipedia",
        "The Nobel Prize in Physics 2024 was awarded to John Hopfield and Geoffrey Hinton.",
    ),
    hit(
        "https://www.nobelprize.org/prizes/physics/2024/summary/",
        "The Nobel Prize in Physics 2024 - NobelPrize.org",
        "The Nobel Prize in Physics 2024 laureates are Hopfield and Hinton, pioneers of machine learning.",
    ),
]

WORK_HITS = [
    hit(
        "https://hf.blog/kv/2024-physics",
        "Why Hopfield and Hinton won the 2024 physics Nobel",
        "Awarded for foundational discoveries on artificial neural networks and machine learning.",
    ),
    hit(
        "https://www.science.org/nobel-2024-neural-networks",
        "Nobel 2024: artificial neural networks recognized",
        "The prize honors machine learning work on Hopfield networks and Boltzmann machines.",
    ),
]

IRRELEVANT_HITS = [
    hit(
        "https://recipes.example.com/pasta",
        "Best pasta carbonara recipe",
        "Cook the spaghetti slowly; the sauce needs eggs, cheese and pepper.",
    ),
]


class MockProvider:
    """Returns scripted results by matching substrings of the query."""

    name = "mock"

    def __init__(self, script: list[tuple[str, list[SearchHit]]]):
        """script: list of (substring-or-'*', hits). First match wins; '*' matches all."""
        self.script = script
        self.queries: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.queries.append(query)
        for pattern, hits in self.script:
            if pattern == "*" or pattern.lower() in query.lower():
                return hits[:max_results]
        return []


@pytest.fixture
def task() -> TaskSpec:
    return make_task()
