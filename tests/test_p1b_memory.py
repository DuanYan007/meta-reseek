"""P1-b memory foundation tests (offline; task-book section 5).

覆盖：WorkingMemory 派生字段、EpisodicMemory 持久化/读取/去重/查询/版本校验、
经历与 P0 轨迹的一致性、以及记忆开关不影响原检索行为。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

from meta_reseek.memory import EpisodicMemory, WorkingMemory, episodes_from_log
from meta_reseek.memory.episodic import SCHEMA, SCHEMA_VERSION
from meta_reseek.metacog.controller import MetacognitiveController

from conftest import MockProvider, WINNERS_HITS, WORK_HITS, make_task


def _run(task=None, provider=None):
    task = task or make_task(max_rounds=6)
    provider = provider or MockProvider([("*", WINNERS_HITS + WORK_HITS)])
    log = MetacognitiveController(task, provider).run()
    return task, log


# ---------------------------------------------------------------- Working --
def test_working_memory_view_fields():
    task, log = _run()
    wm = WorkingMemory(task, log, recent_rounds=2)
    snap = wm.snapshot()

    # 当前覆盖状态与缺口（来自最近 perception；K=2）
    assert set(snap["coverage"]) == {"winners", "work"}
    assert all("gap" in v for v in snap["coverage"].values())
    gaps = snap["gaps"]
    assert all(g >= 0 for g in gaps.values())

    # 已尝试查询 = 全部 search 轮查询，且不重复
    queries = snap["tried_queries"]
    assert queries and len(queries) == len(set(queries))
    assert queries == wm.tried_queries()

    # 最近 N 轮策略带理由
    strat = snap["recent_strategies"]
    assert 1 <= len(strat) <= 2
    assert all(s["strategy"] and s["query"] and s["reason"] for s in strat)

    # 最近一轮反馈与通道状态
    assert snap["last_feedback"]["effect"] in {"helpful", "neutral", "stalled"}
    assert snap["channel_state"] == {"provider_error": False, "provider_retries": 0}

    summary = wm.context_summary()
    assert "未满足缺口" in summary and "已尝试查询" in summary


def test_working_memory_reflects_gaps_mid_collection():
    # 只给 winners 证据：work 缺口应为 K
    task = make_task(max_rounds=8)
    provider = MockProvider([("*", WINNERS_HITS)])
    log = MetacognitiveController(task, provider).run()
    wm = WorkingMemory(task, log)
    assert wm.gaps().get("work") == task.min_relevant_per_subq


# --------------------------------------------------------------- Episodic --
def test_episode_schema_and_full_experience_chain():
    task, log = _run()
    eps = episodes_from_log(log)
    search_eps = [e for e in eps if e["kind"] == "search"]
    stop_eps = [e for e in eps if e["kind"] == "stop"]
    assert search_eps and len(stop_eps) == 1

    for e in eps:
        assert e["schema"] == SCHEMA and e["version"] == SCHEMA_VERSION
        assert e["before_state"]["perception"] and e["before_state"]["evaluation"]
    e = search_eps[0]
    # 完整链路：调整前状态 → 动作 → 理由 → 检索反馈 → 实际结果
    assert e["action"]["strategy"] and e["action"]["query"]
    assert e["action"].get("reason")  # 调整理由
    assert e["search_feedback"]["ingest"] is not None
    assert e["outcome"]["effect"] in {"helpful", "neutral", "stalled"}
    assert e["outcome"]["new_items"] >= 0


def test_episodic_save_load_roundtrip_and_dedup(tmp_path):
    task, log = _run()
    mem = EpisodicMemory()
    mem.extend_from_log(log)
    path = mem.save(tmp_path / "mem.jsonl")
    assert path.exists()

    loaded = EpisodicMemory.load(path)
    assert loaded.records == mem.records

    # 去重：同一 (task, run_id, round_idx) 重复导入不产生重复条目
    loaded.extend_from_log(log)
    assert len(loaded.records) == len(mem.records)

    # 每行都是合法 JSON（离线可读）
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(mem.records)
    json.loads(lines[0])


def test_episodic_query_interface():
    # 构造会出现 target=work 的 broaden 轮次的运行
    task = make_task(max_rounds=8)
    provider = MockProvider([
        ("2024 nobel prize in physics", WINNERS_HITS),          # seed
        ("what specific work", WORK_HITS),                      # broaden -> work
        ("*", WINNERS_HITS + WORK_HITS),
    ])
    log = MetacognitiveController(task, provider).run()
    mem = EpisodicMemory()
    mem.extend_from_log(log)

    assert all(r["task"] == task.name for r in mem.query(task=task.name))
    subq_rows = mem.query(subq="work")
    assert subq_rows and all(
        (r.get("action") or {}).get("target_subq") == "work" for r in subq_rows
    )
    assert len(mem.query(strategy="initial")) == 1  # 首轮 initial 只有一条
    # 组合条件
    assert mem.query(task=task.name, subq="work", strategy="broaden") == [
        r for r in mem.query(subq="work") if r["action"]["strategy"] == "broaden"
    ]


def test_episodic_rejects_unknown_schema_or_version():
    import pytest

    mem = EpisodicMemory()
    good = {
        "schema": SCHEMA, "version": SCHEMA_VERSION, "kind": "stop",
        "task": "t", "run_id": "t@x", "round_idx": 1, "before_state": {},
    }
    mem.append(good)
    with pytest.raises(ValueError):
        mem.append({**good, "schema": "other/thing"})
    with pytest.raises(ValueError):
        mem.append({**good, "version": 99})
    with pytest.raises(ValueError):
        mem.append({**good, "kind": "search"})  # search 必须带 action+outcome


# ----------------------------------------------------- consistency & off --
def test_episodes_match_trace_records():
    """经历记录与 P0 JSON 轨迹逐字段一致（一致性检查，验收第 3/4 项的离线版）。"""
    task, log = _run()
    eps = episodes_from_log(log)
    search_eps = sorted((e for e in eps if e["kind"] == "search"), key=lambda e: e["round_idx"])
    trace_rounds = [r.as_dict() for r in log.records if r.decision == "search"]
    assert len(search_eps) == len(trace_rounds)
    for e, tr in zip(search_eps, trace_rounds):
        assert e["round_idx"] == tr["round_idx"]
        assert e["before_state"]["perception"] == tr["perception"]
        assert e["before_state"]["evaluation"] == tr["evaluation"]
        assert e["action"] == tr["action"]
        assert e["search_feedback"]["ingest"] == tr["ingest"]
        assert e["outcome"]["effect"] == tr["feedback"]["effect"]


def test_memory_wiring_does_not_change_retrieval_behaviour():
    """记忆开关等价：不接记忆时与原 P0 行为完全一致（同一 mock 世界跑两遍）。"""
    task, log_a = _run()
    _, log_b = _run(task=task)
    assert log_a.as_dict()["rounds"] == log_b.as_dict()["rounds"]

    # 投影经历也不改变轨迹本身（只读）
    episodes_from_log(log_a)
    assert log_a.as_dict()["rounds"] == log_b.as_dict()["rounds"]
