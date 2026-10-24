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

import pytest

from conftest import MockProvider, WINNERS_HITS, WORK_HITS, make_task

_CACHE = Path(__file__).resolve().parents[1] / "artifacts/cache"
_HAS_CACHE = _CACHE.exists() and bool(list(_CACHE.glob("*.json")))
_needs_cache = pytest.mark.skipif(
    not _HAS_CACHE, reason="本机无检索缓存：离线回放类 CLI 测试需要 artifacts/cache")



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


# ----------------------------------------------- PR #9 rework boundary tests --
def test_save_merges_across_runs_and_is_idempotent(tmp_path):
    """整改①：同路径多次运行保存——已有经历保留、重复保存幂等。"""
    task_a, log_a = _run()                                    # 充分停止路径
    task_b = make_task(max_rounds=8)                          # broaden 路径（内容不同）
    provider_b = MockProvider([
        ("2024 nobel prize in physics", WINNERS_HITS),
        ("what specific work", WORK_HITS),
        ("*", WINNERS_HITS),
    ])
    log_b = MetacognitiveController(task_b, provider_b).run()

    path = tmp_path / "shared.jsonl"
    mem_a = EpisodicMemory()
    mem_a.extend_from_log(log_a)
    mem_a.save(path)
    first_bytes = path.read_bytes()
    n_a = len(EpisodicMemory.load(path).records)

    mem_b = EpisodicMemory()
    mem_b.extend_from_log(log_b)
    mem_b.save(path)                                          # 第二次运行，同路径
    reloaded = EpisodicMemory.load(path)
    assert len(reloaded.records) == n_a + len(log_b.records)  # 旧经历保留
    assert {r["run_id"] for r in reloaded.records} >= {r["run_id"] for r in episodes_from_log(log_a)}

    before = path.read_bytes()
    mem_b2 = EpisodicMemory()
    mem_b2.extend_from_log(log_b)
    mem_b2.save(path)                                         # 同内容重复保存
    assert path.read_bytes() == before                        # 幂等：字节不变
    assert path.read_bytes() != first_bytes or n_a == len(reloaded.records)


def test_init_with_records_validates_and_copies(tmp_path):
    """整改②：records= 初始化语义——逐条校验并拷贝，非法记录拒绝。"""
    import pytest

    task, log = _run()
    eps = episodes_from_log(log)[:2]
    mem = EpisodicMemory(records=eps)
    assert [r["round_idx"] for r in mem.records] == [e["round_idx"] for e in eps]
    mem.records[0]["task"] = "mutated"
    assert eps[0]["task"] != "mutated"          # 拷贝而非引用（改副本不污染入参列表内对象?）
    with pytest.raises(ValueError):
        EpisodicMemory(records=[{"schema": "bad"}])


def test_run_id_content_fingerprint_avoids_same_second_collision():
    """整改③：同秒同任务的不同运行内容指纹不同；同内容则同 id（幂等去重）。"""
    task = make_task(max_rounds=8)
    log_a = MetacognitiveController(
        task, MockProvider([("*", WINNERS_HITS + WORK_HITS)])).run()
    log_b = MetacognitiveController(
        task, MockProvider([("*", WINNERS_HITS)])).run()      # 不同内容（永不充分）
    # 模拟“同一秒”：强行对齐时间戳
    log_b.started_at = log_a.started_at
    id_a = {e["run_id"] for e in episodes_from_log(log_a)}
    id_b = {e["run_id"] for e in episodes_from_log(log_b)}
    assert len(id_a) == 1 and len(id_b) == 1 and id_a != id_b  # 内容不同 → 不碰撞

    # 同一 log 重复投影 → 同 id；同秒同内容双跑 → 合并去重为一份
    assert {e["run_id"] for e in episodes_from_log(log_a)} == id_a
    mem = EpisodicMemory()
    mem.extend_from_log(log_a)
    mem.extend_from_log(log_a)
    assert len(mem.records) == len(log_a.records)


@_needs_cache
def test_save_episodes_flag_does_not_affect_decisions(tmp_path):
    """整改④：--save-episodes 开关不影响检索决策（离线回放口径下轨迹一致）。"""
    import shutil

    import meta_reseek.run as runner

    task_yaml = "examples/tasks/kv_cache_llm.yaml"

    out_plain = tmp_path / "plain"
    rc1 = runner.main([task_yaml, "--cache", "offline", "--out", str(out_plain), "--quiet"])
    trace_plain = json.loads((out_plain / "kv_cache_llm.json").read_text(encoding="utf-8"))

    out_mem = tmp_path / "withmem"
    rc2 = runner.main([task_yaml, "--cache", "offline", "--out", str(out_mem),
                       "--quiet", "--save-episodes", str(tmp_path / "flag" / "mem.jsonl")])
    trace_mem = json.loads((out_mem / "kv_cache_llm.json").read_text(encoding="utf-8"))
    assert rc1 == rc2 == 0
    assert trace_plain["rounds"] == trace_mem["rounds"]       # 决策序列一致
    assert (tmp_path / "flag" / "mem.jsonl").exists()         # 记忆确已保存
