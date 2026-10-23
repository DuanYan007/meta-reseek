"""Task specification: a research question decomposed into sub-questions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .textutil import words


@dataclass
class SubQuestion:
    """One verifiable piece of the overall question.

    ``keywords`` are retrieval hints: terms expected to appear in documents
    that answer this sub-question. They steer lexical relevance scoring and
    query specialization, not the final answer.
    """

    id: str
    text: str
    keywords: list[str] = field(default_factory=list)
    alt_queries: list[str] = field(default_factory=list)

    @property
    def terms(self) -> list[str]:
        """Scoring terms in priority order: keywords first (higher signal),
        then content words of the question text.

        Multi-word terms stay whole; a single word already covered by a
        multi-word term is not added again.
        """
        terms: list[str] = []
        seen: set[str] = set()
        covered: set[str] = set()
        for raw in list(self.keywords) + list(self.text.split()):
            ws = words(raw)
            if not ws:
                continue
            if len(ws) > 1:
                key = " ".join(ws)
                if key not in seen:
                    seen.add(key)
                    terms.append(key)
                    covered.update(ws)
            elif ws[0] not in seen and ws[0] not in covered:
                seen.add(ws[0])
                terms.append(ws[0])
        return terms


@dataclass
class TaskSpec:
    """A retrieval task with explicit, inspectable stop criteria."""

    name: str
    question: str
    seed_query: str
    sub_questions: list[SubQuestion]
    min_relevant_per_subq: int = 2  # K: relevant items needed per sub-question
    max_rounds: int = 6

    def __post_init__(self) -> None:
        # Terms shared by >=2 sub-questions (e.g. "nobel", "physics") carry
        # little evidence about WHICH sub-question a document answers; the
        # relevance scorer down-weights them.
        owners: dict[str, int] = {}
        for sq in self.sub_questions:
            for term in sq.terms:
                owners[term] = owners.get(term, 0) + 1
        self.common_terms = {t for t, n in owners.items() if n >= 2}

    def subq(self, subq_id: str) -> SubQuestion:
        for sq in self.sub_questions:
            if sq.id == subq_id:
                return sq
        raise KeyError(subq_id)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TaskSpec":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        subqs = [
            SubQuestion(
                id=s["id"],
                text=s["text"],
                keywords=list(s.get("keywords", [])),
                alt_queries=list(s.get("alt_queries", [])),
            )
            for s in raw["sub_questions"]
        ]
        return cls(
            name=raw["name"],
            question=raw["question"],
            seed_query=raw.get("seed_query", raw["question"]),
            sub_questions=subqs,
            min_relevant_per_subq=int(raw.get("min_relevant_per_subq", 2)),
            max_rounds=int(raw.get("max_rounds", 6)),
        )
