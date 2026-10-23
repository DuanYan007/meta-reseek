"""Adjustment: choose the next search action based on the assessment.

Baseline rule-based policy. Every choice carries the reason that produced
it; P1+ can swap in a learned or LLM policy behind this same function.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..task import TaskSpec
from .evaluation import Assessment
from .perception import Snapshot


@dataclass
class SearchAction:
    strategy: str  # initial | target_weakest | specialize | broaden | diversify
    query: str
    target_subq: str | None
    reason: str

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "query": self.query,
            "target_subq": self.target_subq,
            "reason": self.reason,
        }


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


def initial_action(task: TaskSpec) -> SearchAction:
    return SearchAction(
        strategy="initial",
        query=task.seed_query,
        target_subq=None,
        reason="首轮检索：使用任务自带的种子查询。",
    )


def _candidates_for(sq, task: TaskSpec) -> list[str]:
    """Query variants for one sub-question, in deterministic priority order."""
    out = [sq.text] + list(sq.alt_queries)
    if sq.keywords:
        out.append(" ".join(sq.keywords))
    return out


def decide_action(
    snapshot: Snapshot,
    assessment: Assessment,
    task: TaskSpec,
    used_queries: set[str],
) -> SearchAction:
    """Pick the next query. Never repeats an already-used query verbatim."""
    used = {_norm(q) for q in used_queries}
    k = task.min_relevant_per_subq

    # Priority 1: sub-questions with zero relevant evidence -> broaden.
    empty = [sid for sid, v in snapshot.per_subq.items() if v.relevant_count == 0]
    if empty:
        sid = empty[0]
        sq = task.subq(sid)
        for cand in _candidates_for(sq, task):
            if _norm(cand) not in used:
                return SearchAction(
                    strategy="broaden",
                    query=cand,
                    target_subq=sid,
                    reason=f"子问题 {sid} 尚无任何相关证据，优先补齐：改用其候选查询变体。",
                )
        return SearchAction(
            strategy="broaden",
            query=f"{sq.text} (round {snapshot.round_idx})",
            target_subq=sid,
            reason=f"子问题 {sid} 无证据且预设变体已用尽，追加轮次限定词强制探索。",
        )

    # Priority 2: diversify when coverage is halfway but sources are thin.
    coverage = snapshot.coverage_score(k)
    if coverage >= 0.5 and snapshot.domain_count < 2:
        sid = assessment.weakest or snapshot.weakest_subq(k)
        sq = task.subq(sid)
        for cand in _candidates_for(sq, task):
            if _norm(cand) not in used:
                return SearchAction(
                    strategy="diversify",
                    query=cand,
                    target_subq=sid,
                    reason=f"覆盖已达 {coverage:.2f} 但来源域仅 {snapshot.domain_count} 个，换查询变体引入新来源。",
                )

    # Default: attack the weakest sub-question; prefer unused variants.
    sid = snapshot.weakest_subq(k)
    sq = task.subq(sid)
    base_used = _norm(sq.text) in used
    for cand in _candidates_for(sq, task):
        if _norm(cand) not in used:
            strategy = "specialize" if base_used else "target_weakest"
            why = (
                f"基查询已试过，切换到该子问题的其他查询变体。"
                if base_used
                else "直接以最薄弱子问题的表述检索。"
            )
            return SearchAction(
                strategy=strategy,
                query=cand,
                target_subq=sid,
                reason=f"评价指向最薄弱子问题 {sid}（{snapshot.per_subq[sid].relevant_count}/{k}）。{why}",
            )
    return SearchAction(
        strategy="specialize",
        query=f"{sq.text} (round {snapshot.round_idx})",
        target_subq=sid,
        reason=f"子问题 {sid} 的全部变体已用尽，追加轮次限定词继续探索。",
    )
