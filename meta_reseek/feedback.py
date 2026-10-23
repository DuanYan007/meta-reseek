"""Feedback: record every round's decision and measure whether it helped."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RoundRecord:
    round_idx: int
    perception: dict = field(default_factory=dict)
    evaluation: dict = field(default_factory=dict)
    decision: str = ""          # search | stop_sufficient | stop_diminishing | stop_forced
    decision_reason: str = ""
    action: dict | None = None  # strategy/query/target/reason
    ingest: dict | None = None  # candidates/added/duplicates/irrelevant
    feedback: dict | None = None

    def as_dict(self) -> dict:
        return {
            "round_idx": self.round_idx,
            "perception": self.perception,
            "evaluation": self.evaluation,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "action": self.action,
            "ingest": self.ingest,
            "feedback": self.feedback,
        }


class DecisionLog:
    """Append-only record of the whole run; becomes the JSON trace."""

    def __init__(self, task_name: str, config: dict) -> None:
        self.task_name = task_name
        self.config = config
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.records: list[RoundRecord] = []
        self.evidence: list[dict] = []  # final evidence list (set at run end)

    def add(self, record: RoundRecord) -> None:
        self.records.append(record)

    # -- analysis used by the controller ---------------------------------

    def recent_gains(self) -> list[int]:
        """New *relevant* items per completed search round, in order."""
        gains: list[int] = []
        for r in self.records:
            if r.feedback:
                gains.append(int(r.feedback.get("new_relevant_total", 0)))
        return gains

    def recent_errors(self) -> list[bool]:
        """Whether each completed search round failed at the transport level."""
        errors: list[bool] = []
        for r in self.records:
            if r.feedback:
                errors.append(bool(r.feedback.get("provider_error", False)))
        return errors

    def used_queries(self) -> set[str]:
        return {
            r.action["query"]
            for r in self.records
            if r.action and r.action.get("query")
        }

    # -- outputs ----------------------------------------------------------

    def summary(self) -> dict:
        stops = [r.decision for r in self.records if r.decision.startswith("stop")]
        last_eval = next(
            (r.evaluation for r in reversed(self.records) if r.evaluation), {}
        )
        last_perc = next(
            (r.perception for r in reversed(self.records) if r.perception), {}
        )
        searches = [r for r in self.records if r.decision == "search"]
        effects = [r.feedback.get("effect") for r in searches if r.feedback]
        return {
            "task": self.task_name,
            "rounds_total": len(self.records),
            "search_rounds": len(searches),
            "stop_decision": stops[-1] if stops else "none",
            "final_score": last_eval.get("score"),
            "final_verdict": last_eval.get("verdict"),
            "final_perception": last_perc,
            "effect_counts": {
                e: effects.count(e) for e in ("helpful", "neutral", "stalled") if e in effects
            },
        }

    def as_dict(self) -> dict:
        return {
            "task": self.task_name,
            "config": self.config,
            "started_at": self.started_at,
            "rounds": [r.as_dict() for r in self.records],
            "evidence": self.evidence,
            "summary": self.summary(),
        }
