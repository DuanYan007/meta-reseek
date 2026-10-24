"""Working Memory: a read-only view over the P0 decision log.

任务书第二节要求的五项内容全部从现有 DecisionLog（RoundRecord）派生，
不复制、不缓存、不参与决策——P0 控制器对此类无感知：
- 当前子问题及证据覆盖状态      <- 最近一条 perception
- 最近若干轮检索策略与理由       <- 最近 N 条 search 记录的 action
- 已尝试的查询                  <- 全部 action.query
- 尚未满足的证据缺口            <- 最近 perception 中 relevant_count < K 的子问题
- 最近一轮反馈及检索通道状态     <- 最近一条 feedback（含 provider_error/retries）
"""

from __future__ import annotations

from ..feedback import DecisionLog
from ..task import TaskSpec


class WorkingMemory:
    def __init__(self, task: TaskSpec, log: DecisionLog, recent_rounds: int = 3):
        self.task = task
        self.log = log
        self.recent_rounds = recent_rounds

    # -- derived views ------------------------------------------------------

    def _last_perception(self) -> dict:
        for record in reversed(self.log.records):
            if record.perception:
                return record.perception
        return {}

    def _last_feedback(self) -> dict | None:
        for record in reversed(self.log.records):
            if record.feedback:
                return record.feedback
        return None

    def coverage(self) -> dict[str, dict]:
        """子问题 → {relevant_count, 缺口条数}（K = min_relevant_per_subq）。"""
        perc = self._last_perception()
        k = self.task.min_relevant_per_subq
        out = {}
        for sid, view in (perc.get("per_subq") or {}).items():
            count = view["relevant_count"]
            out[sid] = {"relevant_count": count, "gap": max(k - count, 0)}
        return out

    def gaps(self) -> dict[str, int]:
        """尚未满足的证据缺口（子问题 → 还差几条相关证据）。"""
        return {sid: v["gap"] for sid, v in self.coverage().items() if v["gap"] > 0}

    def tried_queries(self) -> list[str]:
        return [r.action["query"] for r in self.log.records if r.action and r.action.get("query")]

    def recent_strategies(self) -> list[dict]:
        """最近 N 轮检索策略与理由。"""
        rows = [
            {
                "round": r.round_idx,
                "strategy": r.action["strategy"],
                "query": r.action["query"],
                "target_subq": r.action.get("target_subq"),
                "reason": r.action.get("reason"),
            }
            for r in self.log.records
            if r.decision == "search" and r.action
        ]
        return rows[-self.recent_rounds:]

    def channel_state(self) -> dict:
        fb = self._last_feedback() or {}
        return {
            "provider_error": bool(fb.get("provider_error", False)),
            "provider_retries": int(fb.get("provider_retries", 0)),
        }

    # -- outputs -------------------------------------------------------------

    def snapshot(self) -> dict:
        """当前任务上下文（全部由 DecisionLog 派生）。"""
        return {
            "task": self.task.name,
            "coverage": self.coverage(),
            "gaps": self.gaps(),
            "recent_strategies": self.recent_strategies(),
            "tried_queries": self.tried_queries(),
            "last_feedback": self._last_feedback(),
            "channel_state": self.channel_state(),
            "rounds_so_far": len(self.log.records),
        }

    def context_summary(self) -> str:
        """人类可读的任务上下文（验收第 1 项演示用）。"""
        snap = self.snapshot()
        cov = "，".join(f"{sid}:{v['relevant_count']}" for sid, v in snap["coverage"].items())
        gaps = "、".join(f"{sid}(-{g})" for sid, g in snap["gaps"].items()) or "无"
        lines = [
            f"[WorkingMemory | {snap['task']}] 已进行 {snap['rounds_so_far']} 条记录",
            f"证据覆盖：{cov or '（空）'}",
            f"未满足缺口：{gaps}",
            f"已尝试查询（{len(snap['tried_queries'])}）："
            + "；".join(q for q in snap["tried_queries"]),
        ]
        for s in snap["recent_strategies"]:
            lines.append(
                f"最近策略 R{s['round']}：{s['strategy']} → {s['query']!r}"
                f"（目标 {s['target_subq']}）理由：{s['reason']}"
            )
        fb = snap["last_feedback"] or {}
        if fb:
            lines.append(
                f"最近反馈：新增文档 {fb.get('new_items')} / 匹配增量 {fb.get('new_relevant_total')}"
                f"，效果 {fb.get('effect')}，通道错误={fb.get('provider_error', False)}"
                f"，重试 {fb.get('provider_retries', 0)} 次"
            )
        return "\n".join(lines)
