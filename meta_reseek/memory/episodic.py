"""Episodic Memory: versioned JSONL persistence of complete task experiences.

每条经历（ExperienceRecord v1）保留任务书第三节要求的完整链路：

    调整前状态（perception+evaluation） → 调整动作（strategy/query/target）
    → 调整理由（action.reason / decision_reason） → 检索反馈（ingest+通道状态）
    → 实际结果（effect/新增文档/匹配增量/覆盖计数）

投影源是 P0 DecisionLog 的 RoundRecord——不重复采集、不改动控制器。
停止记录（无动作/无结果）以 kind="stop" 保存，只含前状态与停止理由。

字段含义（schema: meta-reseek/episodic-v1）：
- schema/version     格式标识，读取时校验
- kind               "search"（完整经历）| "stop"（终止记录）
- run_id             一次运行的标识（task + DecisionLog.started_at），同 run 去重键之一
- before_state       调整前感知与评价（= RoundRecord.perception/evaluation）
- action             调整动作与理由（= RoundRecord.action）
- search_feedback    检索执行反馈（= RoundRecord.ingest + provider_error/retries）
- outcome            实际结果（= RoundRecord.feedback 中的效果与增量）
"""

from __future__ import annotations

import json
from pathlib import Path

from ..feedback import DecisionLog

SCHEMA = "meta-reseek/episodic"
SCHEMA_VERSION = 1


def episodes_from_log(log: DecisionLog) -> list[dict]:
    """把一次运行的 DecisionLog 投影为经历记录列表（不落盘）。"""
    run_id = f"{log.task_name}@{log.started_at}"
    out = []
    for r in log.records:
        base = {
            "schema": SCHEMA,
            "version": SCHEMA_VERSION,
            "kind": "stop" if r.decision.startswith("stop") else "search",
            "task": log.task_name,
            "run_id": run_id,
            "round_idx": r.round_idx,
            "decision": r.decision,
            "decision_reason": r.decision_reason,
            "before_state": {"perception": r.perception, "evaluation": r.evaluation},
        }
        if base["kind"] == "search":
            base["action"] = r.action
            base["search_feedback"] = {
                "ingest": r.ingest,
                "provider_error": (r.feedback or {}).get("provider_error", False),
                "provider_retries": (r.feedback or {}).get("provider_retries", 0),
            }
            fb = r.feedback or {}
            base["outcome"] = {
                "effect": fb.get("effect"),
                "new_items": fb.get("new_items"),
                "new_relevant_total": fb.get("new_relevant_total"),
                "new_relevant_for_target": fb.get("new_relevant_for_target"),
                "counts_after": fb.get("counts_after"),
            }
        out.append(base)
    return out


class EpisodicMemory:
    """JSONL 经历库：追加保存、去重加载、最小查询。完全离线，仅标准库。"""

    def __init__(self, records: list[dict] | None = None):
        self.records: list[dict] = []

    # -- 写 ----------------------------------------------------------------

    def append(self, record: dict, dedup: bool = True) -> bool:
        """追加一条经历；dedup=True 时 (task, run_id, round_idx) 相同的旧记录被替换。"""
        self._validate(record)
        if dedup:
            key = (record["task"], record["run_id"], record["round_idx"])
            self.records = [r for r in self.records
                            if (r["task"], r["run_id"], r["round_idx"]) != key]
        self.records.append(record)
        return True

    def extend_from_log(self, log: DecisionLog) -> int:
        for record in episodes_from_log(log):
            self.append(record)
        return len(episodes_from_log(log))

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for record in self.records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    # -- 读 ----------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "EpisodicMemory":
        mem = cls()
        with Path(path).open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                mem.append(json.loads(line))  # append 内部完成校验与去重
        return mem

    def query(self, task: str | None = None, subq: str | None = None,
              strategy: str | None = None) -> list[dict]:
        """按任务 / 目标子问题 / 策略类型检索经历（各条件 AND）。"""
        rows = []
        for r in self.records:
            if task is not None and r["task"] != task:
                continue
            if subq is not None and (r.get("action") or {}).get("target_subq") != subq:
                continue
            if strategy is not None and (r.get("action") or {}).get("strategy") != strategy:
                continue
            rows.append(r)
        return rows

    # -- 内部 ---------------------------------------------------------------

    @staticmethod
    def _validate(record: dict) -> None:
        if record.get("schema") != SCHEMA:
            raise ValueError(f"unknown schema: {record.get('schema')!r}")
        if record.get("version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported version: {record.get('version')!r}")
        for field in ("kind", "task", "run_id", "round_idx", "before_state"):
            if field not in record:
                raise ValueError(f"missing field: {field}")
        if record["kind"] not in {"search", "stop"}:
            raise ValueError(f"bad kind: {record['kind']!r}")
        if record["kind"] == "search" and ("action" not in record or "outcome" not in record):
            raise ValueError("search episode requires action+outcome")
