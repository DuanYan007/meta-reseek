"""Controller: the P0 metacognitive loop.

Perception -> Evaluation -> Adjustment -> Feedback, one RoundRecord per
round, ending in an explicit stop decision (sufficient / diminishing /
forced). The whole run is serialized into an inspectable trace.
"""

from __future__ import annotations

from typing import Any, Callable

from ..evidence import EvidenceStore, IngestReport
from ..feedback import DecisionLog, RoundRecord
from ..search.base import SearchProvider
from ..task import TaskSpec
from .adjustment import SearchAction, decide_action, initial_action
from .evaluation import evaluate
from .perception import perceive
from . import evaluation as eval_cfg

RunTrace = dict[str, Any]


class MetacognitiveController:
    def __init__(
        self,
        task: TaskSpec,
        provider: SearchProvider,
        max_rounds: int | None = None,
        max_results: int = 5,
        emit: Callable[[str], None] | None = None,
    ) -> None:
        self.task = task
        self.provider = provider
        self.max_rounds = max_rounds or task.max_rounds
        self.max_results = max_results
        self._emit = emit or (lambda _msg: None)

    # ------------------------------------------------------------------

    def run(self) -> DecisionLog:
        task = self.task
        store = EvidenceStore()
        log = DecisionLog(
            task.name,
            config={
                "provider": self.provider.name,
                "max_rounds": self.max_rounds,
                "max_results": self.max_results,
                "min_relevant_per_subq": task.min_relevant_per_subq,
                "weights": {
                    "coverage": eval_cfg.W_COVERAGE,
                    "diversity": eval_cfg.W_DIVERSITY,
                },
                "diversity_target": eval_cfg.DIVERSITY_TARGET,
                "stall_window": eval_cfg.STALL_WINDOW,
                "stall_gain": eval_cfg.STALL_GAIN,
            },
        )
        counts_before = {sq.id: 0 for sq in task.sub_questions}
        stopped = False

        for round_idx in range(1, self.max_rounds + 1):
            # 1) PERCEPTION  2) EVALUATION
            snap = perceive(store, task, round_idx)
            assessment = evaluate(
                snap, task, log.recent_gains(), self._error_window(log)
            )

            if round_idx > 1 and assessment.verdict in {"sufficient", "diminishing"}:
                self._emit_stop(round_idx, snap, assessment)
                log.add(
                    RoundRecord(
                        round_idx=round_idx,
                        perception=snap.as_dict(),
                        evaluation=assessment.as_dict(),
                        decision=f"stop_{assessment.verdict}",
                        decision_reason=assessment.rationale,
                    )
                )
                stopped = True
                break

            # 3) ADJUSTMENT (stop was judged unnecessary -> choose next query)
            if round_idx == 1:
                action = initial_action(task)
            else:
                action = decide_action(snap, assessment, task, log.used_queries())

            self._emit(
                f"[Round {round_idx}] 感知: 证据 {snap.total_items} 条 | "
                + " | ".join(
                    f"{sid} {v.relevant_count}/{task.min_relevant_per_subq}"
                    for sid, v in snap.per_subq.items()
                )
                + f" | 来源域 {snap.domain_count}"
            )
            self._emit(
                f"[Round {round_idx}] 评价: score {assessment.score:.2f} → "
                f"{assessment.verdict}（{assessment.rationale}）"
            )
            self._emit(
                f"[Round {round_idx}] 决策: {action.strategy} → 检索 {action.query!r}"
                + (f"（目标: {action.target_subq}）" if action.target_subq else "")
                + f"｜理由: {action.reason}"
            )

            record = RoundRecord(
                round_idx=round_idx,
                perception=snap.as_dict(),
                evaluation=assessment.as_dict(),
                decision="search",
                decision_reason=assessment.rationale,
                action=action.as_dict(),
            )

            # 4) ACT: real external search + evidence ingestion
            hits = self.provider.search(action.query, max_results=self.max_results)
            report = store.ingest(
                hits,
                task=task,
                round_idx=round_idx,
                query_used=action.query,
                strategy=action.strategy,
            )
            self._emit(
                f"[Round {round_idx}] 执行: 候选 {report.candidates} → 采纳 {report.added}"
                f"（重复 {report.duplicates}，离题 {report.irrelevant}）"
            )

            # 5) FEEDBACK: did the adjustment actually improve the state?
            feedback = self._measure_feedback(action, report, store, counts_before)
            feedback["provider_error"] = bool(
                getattr(self.provider, "last_error", None)
            )
            record.ingest = report.as_dict()
            record.feedback = feedback
            log.add(record)
            counts_before = {
                sq.id: len(store.relevant(sq)) for sq in task.sub_questions
            }
            err_note = "，本轮检索通道故障" if feedback["provider_error"] else ""
            self._emit(
                f"[Round {round_idx}] 反馈: 新增相关 {feedback['new_relevant_total']} 条"
                + (
                    f"（目标 {feedback['target_subq']} +{feedback['new_relevant_for_target']}）"
                    if feedback.get("target_subq")
                    else ""
                )
                + f" → 判定 {feedback['effect']}{err_note}"
            )

        if not stopped:
            # max_rounds exhausted: final honest check instead of silent exit
            final_idx = self.max_rounds + 1
            snap = perceive(store, task, final_idx)
            assessment = evaluate(snap, task, log.recent_gains(), self._error_window(log))
            decision = (
                "stop_sufficient" if assessment.verdict == "sufficient" else "stop_forced"
            )
            reason = (
                assessment.rationale
                if decision == "stop_sufficient"
                else f"已达最大轮数 {self.max_rounds}，主动停止。{assessment.rationale}"
            )
            self._emit_stop(final_idx, snap, assessment, forced=(decision == "stop_forced"))
            log.add(
                RoundRecord(
                    round_idx=final_idx,
                    perception=snap.as_dict(),
                    evaluation=assessment.as_dict(),
                    decision=decision,
                    decision_reason=reason,
                )
            )
        # full evidence list: lets a reviewer audit what the sufficiency
        # verdict was actually based on
        log.evidence = [
            {
                "eid": it.eid,
                "title": it.title,
                "url": it.url,
                "domain": it.domain,
                "round_added": it.round_added,
                "strategy": it.strategy,
                "relevance": {k: round(v, 3) for k, v in it.relevance.items()},
            }
            for it in store.items
        ]
        return log

    # ------------------------------------------------------------------

    @staticmethod
    def _error_window(log: "DecisionLog") -> int:
        return sum(log.recent_errors()[-eval_cfg.STALL_WINDOW:])

    def _measure_feedback(
        self,
        action: SearchAction,
        report: IngestReport,
        store: EvidenceStore,
        counts_before: dict[str, int],
    ) -> dict:
        counts_after = {sq.id: len(store.relevant(sq)) for sq in self.task.sub_questions}
        new_relevant_total = sum(counts_after.values()) - sum(counts_before.values())
        target = action.target_subq
        new_for_target = (counts_after[target] - counts_before[target]) if target else None
        if report.added == 0:
            effect = "stalled"
        elif (new_for_target is not None and new_for_target >= 1) or (
            target is None and new_relevant_total >= 1
        ):
            effect = "helpful"
        else:
            effect = "neutral"
        return {
            "target_subq": target,
            "new_items": report.added,
            "new_relevant_total": new_relevant_total,
            "new_relevant_for_target": new_for_target,
            "counts_after": counts_after,
            "effect": effect,
        }

    def _emit_stop(self, round_idx: int, snap, assessment, forced: bool = False) -> None:
        tag = "强制停止" if forced else "主动停止"
        self._emit(
            f"[Round {round_idx}] 感知: 证据 {snap.total_items} 条 | "
            + " | ".join(
                f"{sid} {v.relevant_count}/{self.task.min_relevant_per_subq}"
                for sid, v in snap.per_subq.items()
            )
            + f" | 来源域 {snap.domain_count}"
        )
        self._emit(
            f"[Round {round_idx}] 评价: score {assessment.score:.2f} → "
            f"{assessment.verdict}（{assessment.rationale}）"
        )
        self._emit(f"[Round {round_idx}] 决策: {tag}。")
