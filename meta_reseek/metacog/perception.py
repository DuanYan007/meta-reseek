"""Perception: turn the raw evidence store into a structured state view."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..evidence import EvidenceStore
from ..task import TaskSpec


@dataclass
class SubqView:
    id: str
    text: str
    relevant_count: int
    best_relevance: float
    domains: list[str] = field(default_factory=list)


@dataclass
class Snapshot:
    """What the agent knows about its own retrieval state at this round."""

    round_idx: int
    total_items: int
    per_subq: dict[str, SubqView] = field(default_factory=dict)
    domain_count: int = 0
    total_rounds_so_far: int = 0
    new_items_last_round: int = 0

    # -- derived metrics (all deterministic) ------------------------------

    def coverage_ratios(self, k: int) -> dict[str, float]:
        """min(count/K, 1) per sub-question."""
        return {
            sid: min(v.relevant_count / k, 1.0) if k else 0.0
            for sid, v in self.per_subq.items()
        }

    def coverage_score(self, k: int) -> float:
        ratios = self.coverage_ratios(k)
        return sum(ratios.values()) / len(ratios) if ratios else 0.0

    def weakest_subq(self, k: int) -> str | None:
        if not self.per_subq:
            return None
        return min(
            self.per_subq,
            key=lambda sid: (self.per_subq[sid].relevant_count, self.per_subq[sid].best_relevance),
        )

    def as_dict(self) -> dict:
        return {
            "round_idx": self.round_idx,
            "total_items": self.total_items,
            "domain_count": self.domain_count,
            "new_items_last_round": self.new_items_last_round,
            "per_subq": {
                sid: {
                    "relevant_count": v.relevant_count,
                    "best_relevance": round(v.best_relevance, 3),
                    "domains": v.domains,
                }
                for sid, v in self.per_subq.items()
            },
        }


def perceive(store: EvidenceStore, task: TaskSpec, round_idx: int) -> Snapshot:
    """Build the round snapshot the evaluator and strategy will reason over."""
    per_subq: dict[str, SubqView] = {}
    for sq in task.sub_questions:
        items = store.relevant(sq)
        per_subq[sq.id] = SubqView(
            id=sq.id,
            text=sq.text,
            relevant_count=len(items),
            best_relevance=max((it.relevance.get(sq.id, 0.0) for it in items), default=0.0),
            domains=sorted({it.domain for it in items}),
        )
    last_round = round_idx - 1 if round_idx > 1 else 0
    return Snapshot(
        round_idx=round_idx,
        total_items=len(store.items),
        per_subq=per_subq,
        domain_count=store.domain_count(),
        total_rounds_so_far=round_idx - 1,
        new_items_last_round=len(store.items_from_round(last_round)),
    )
