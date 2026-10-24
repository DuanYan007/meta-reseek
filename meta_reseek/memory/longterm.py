"""Long-term Memory: cross-task metacognitive experience statistics.

从既有 EpisodicMemory 经历中提取**可追溯**的跨任务策略统计：
- 按任务 × 策略聚合：尝试次数、反馈分布（helpful/neutral/stalled）、
  通道错误次数与重试总数；
- 每个统计格保存来源 episode ID（run_id + round），可回溯原始经历；
- 同一经历重复导入不重复计数（幂等，来源 ID 集合去重）；
- 持久化为 JSON（标准库），重载后统计确定不变；
- schema 版本化，未知版本拒绝。

**口径声明（任务书第二节）**：`effect=helpful` 只是 P0 反馈代理
（本轮新增相关匹配），**不等于真实答案质量提高**；本模块全部统计
字段均为该代理口径，字段含义写入持久化文档的 note 字段。

边界（任务书第五节）：只保存和查询统计，不参与搜索策略选择；
不做自动策略学习 / 参数自更新 / 元元认知校准 / RSI。
"""

from __future__ import annotations

import json
from pathlib import Path

from .episodic import EpisodicMemory

SCHEMA = "meta-reseek/longterm"
SCHEMA_VERSION = 1
NOTE = ("effect=helpful 只是 P0 反馈代理（本轮新增相关匹配/文档采纳），"
        "不等于真实答案质量提高；本统计仅此口径")


def _episode_id(record: dict) -> str:
    return f"{record['run_id']}#R{record['round_idx']}"


class LongTermMemory:
    def __init__(self):
        self.ingested: set[str] = set()          # 已导入的 episode ID
        self.stats: dict[str, dict[str, dict]] = {}  # task -> strategy -> cell

    # -- 导入 ----------------------------------------------------------------

    def ingest(self, episodes) -> int:
        """聚合导入经历（EpisodicMemory 或经历 dict 列表）；返回新增条数。

        幂等：已导入过的 episode ID（run_id+round）直接跳过。
        """
        records = episodes.records if isinstance(episodes, EpisodicMemory) else list(episodes)
        added = 0
        for record in records:
            if record.get("kind") != "search":
                continue  # stop 记录无动作/结果，不进策略统计
            eid = _episode_id(record)
            if eid in self.ingested:
                continue
            self.ingested.add(eid)
            action = record.get("action") or {}
            feedback = record.get("search_feedback") or {}
            outcome = record.get("outcome") or {}
            cell = self._cell(record["task"], action.get("strategy") or "unknown")
            cell["attempts"] += 1
            effect = outcome.get("effect")
            if effect is not None:
                cell["effect_counts"][effect] = cell["effect_counts"].get(effect, 0) + 1
                if effect == "helpful":
                    cell["helpful_proxy_count"] += 1
            if feedback.get("provider_error"):
                cell["channel_errors"] += 1
            cell["channel_retries_total"] += int(feedback.get("provider_retries", 0))
            cell["source_episode_ids"].append(eid)
            added += 1
        return added

    def _cell(self, task: str, strategy: str) -> dict:
        return self.stats.setdefault(task, {}).setdefault(strategy, {
            "attempts": 0,
            "effect_counts": {},
            "helpful_proxy_count": 0,
            "channel_errors": 0,
            "channel_retries_total": 0,
            "source_episode_ids": [],
        })

    # -- 查询与核对 -----------------------------------------------------------

    def query(self, task: str | None = None, strategy: str | None = None) -> list[dict]:
        """扁平化查询：任务/策略可任选筛选，返回含溯源 ID 的统计行。"""
        rows = []
        for t in sorted(self.stats):
            if task is not None and t != task:
                continue
            for s in sorted(self.stats[t]):
                if strategy is not None and s != strategy:
                    continue
                rows.append({"task": t, "strategy": s, **self.stats[t][s]})
        return rows

    def reconcile(self, episodes) -> dict:
        """双向核对：用原始经历重算统计，与当前状态逐项比对。

        返回 {ok, mismatches, missing_sources}。提供的经历清单必须覆盖全部
        已导入 episode ID，缺失的列入 missing_sources（此时 ok=False 但原因
        明确为来源不全，而非计数不符）。
        """
        records = episodes.records if isinstance(episodes, EpisodicMemory) else list(episodes)
        provided_ids = {_episode_id(r) for r in records}
        missing_sources = sorted(self.ingested - provided_ids)
        relevant = [r for r in records if _episode_id(r) in self.ingested]
        fresh = LongTermMemory()
        fresh.ingest(relevant)
        mismatches = []
        if missing_sources:
            mismatches.append(
                f"来源清单缺少 {len(missing_sources)} 条已导入经历（missing_sources 字段），无法完整复现"
            )
        own_keys = {(r["task"], r["strategy"]) for r in self.query()}
        fresh_rows = {(r["task"], r["strategy"]): r for r in fresh.query()}
        for row in self.query():
            key = (row["task"], row["strategy"])
            other = fresh_rows.get(key)
            if other is None:
                if not missing_sources:
                    mismatches.append(f"{key}: 统计中存在但来源无法复现")
                continue
            for field in ("attempts", "effect_counts", "helpful_proxy_count",
                          "channel_errors", "channel_retries_total"):
                if row[field] != other[field]:
                    mismatches.append(f"{key}.{field}: {row[field]} != {other[field]}")
        return {"ok": not mismatches, "mismatches": mismatches,
                "missing_sources": missing_sources}

    # -- 持久化 ---------------------------------------------------------------

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "version": SCHEMA_VERSION,
            "note": NOTE,
            "ingested_episode_ids": sorted(self.ingested),
            "stats": self.stats,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # sort_keys + 定定分隔：同状态重复保存字节一致（确定性）
        path.write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "LongTermMemory":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            raise ValueError(f"unknown schema: {data.get('schema')!r}")
        if data.get("version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported version: {data.get('version')!r}")
        mem = cls()
        mem.ingested = set(data["ingested_episode_ids"])
        mem.stats = data["stats"]
        return mem
