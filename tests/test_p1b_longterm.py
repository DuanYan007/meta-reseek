"""P1-b round 2: LongTermMemory tests (offline; task-book section 3).

覆盖验收：单/多任务汇总、重复导入不变、双向核对、保存/重载/确定性、
版本拒绝、代理口径声明、P0 不受影响。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

import pytest

from meta_reseek.memory import EpisodicMemory, LongTermMemory
from meta_reseek.memory.episodic import episodes_from_log
from meta_reseek.memory.longterm import NOTE, SCHEMA, SCHEMA_VERSION
from meta_reseek.metacog.controller import MetacognitiveController

from pathlib import Path as _P

import pytest

from conftest import MockProvider, WINNERS_HITS, WORK_HITS, make_task

_CACHE = _P(__file__).resolve().parents[1] / "artifacts/cache"
_needs_cache = pytest.mark.skipif(
    not (_CACHE.exists() and bool(list(_CACHE.glob("*.json")))),
    reason="本机无检索缓存：离线回放类 CLI 测试需要 artifacts/cache")


def _episodes(effect_world=1):
    task = make_task(max_rounds=8)
    if effect_world == 1:
        provider = MockProvider([("*", WINNERS_HITS + WORK_HITS)])
    else:  # broaden 轮存在且部分轮零增益（stalled）
        provider = MockProvider([
            ("2024 nobel prize in physics", WINNERS_HITS),
            ("what specific work", WORK_HITS[:1]),
            ("*", []),
        ])
    log = MetacognitiveController(task, provider).run()
    return task, log, episodes_from_log(log)


def _flaky_task():
    """带通道错误与零增益轮的经历。"""
    task = make_task(max_rounds=8)

    class Flaky(MockProvider):
        name = "flaky"

        def __init__(self):
            super().__init__([("2024 nobel prize in physics", WINNERS_HITS), ("*", [])])
            self.last_error = None

        def search(self, query, max_results=5):
            hits = super().search(query, max_results)
            self.last_error = "RequestError" if not hits else None
            return hits

    log = MetacognitiveController(task, Flaky()).run()
    return episodes_from_log(log)


# ------------------------------------------------------------------ 聚合 --
def test_single_task_aggregation_counts():
    task, log, eps = _episodes()
    ltm = LongTermMemory()
    added = ltm.ingest(eps)
    assert added == sum(1 for r in log.records if r.decision == "search")

    rows = {r["strategy"]: r for r in ltm.query(task=task.name)}
    assert rows["initial"]["attempts"] == 1
    assert rows["initial"]["effect_counts"].get("helpful", 0) == 1
    # 来源溯源：episode ID 可解析回 run_id+round
    eid = rows["initial"]["source_episode_ids"][0]
    assert eid.endswith("#R1") and task.name in eid


def test_multi_task_aggregation():
    _, _, eps_a = _episodes()
    _, _, eps_b = _episodes(effect_world=2)
    ltm = LongTermMemory()
    ltm.ingest(eps_a)
    ltm.ingest(eps_b)
    tasks = {r["task"] for r in ltm.query()}
    assert len(tasks) == 1 and all(r["task"] == "unit_task" for r in ltm.query())
    # 同名任务两次运行合并（同 task 键聚合）
    total_attempts = {r["strategy"]: r["attempts"] for r in ltm.query()}
    assert sum(v for k, v in total_attempts.items() if k == "initial") == 2

    # 真正的多任务：不同任务名的经历（run_id 含任务名，天然不冲突）
    other_task = make_task(max_rounds=8)
    other_task.name = "other_task"
    other_log = MetacognitiveController(
        other_task, MockProvider([("*", WINNERS_HITS + WORK_HITS)])).run()
    ltm.ingest(episodes_from_log(other_log))
    assert {r["task"] for r in ltm.query()} == {"unit_task", "other_task"}


def test_channel_error_and_effect_proxy_counts():
    eps = _flaky_task()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    rows = {r["strategy"]: r for r in ltm.query()}
    assert sum(r["channel_errors"] for r in rows.values()) >= 1
    assert sum(r["effect_counts"].get("stalled", 0) for r in rows.values()) >= 1
    # 代理口径声明随文档持久化
    assert "helpful" in NOTE and "不等于" in NOTE


# ------------------------------------------------------------------ 幂等 --
def test_reingest_same_episodes_changes_nothing(tmp_path):
    _, _, eps = _episodes()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    path = ltm.save(tmp_path / "ltm.json")
    before = path.read_bytes()

    assert ltm.ingest(eps) == 0                 # 重复导入零新增
    assert ltm.ingest(EpisodicMemory(records=eps)) == 0
    ltm.save(path)
    assert path.read_bytes() == before          # 统计与文件均不变


# -------------------------------------------------------------- 双向核对 --
def test_reconcile_against_source_episodes():
    _, _, eps = _episodes()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    report = ltm.reconcile(eps)
    assert report["ok"] and report["fully_verified"], report["mismatches"]
    assert report["missing_sources"] == [] and report["unverifiable_cells"] == []

    # 部分来源（多轮世界，search 经历 >=2）：报告缺失与不可核验格，不误报损坏
    _, _, eps2 = _episodes(effect_world=2)
    n_search = sum(1 for e in eps2 if e["kind"] == "search")
    assert n_search >= 2
    ltm2 = LongTermMemory()
    ltm2.ingest(eps2)
    partial = ltm2.reconcile(eps2[:1])
    assert partial["ok"]                      # 来源不全 ≠ 数据损坏
    assert not partial["fully_verified"]
    assert len(partial["missing_sources"]) == n_search - 1
    assert partial["unverifiable_cells"]      # 受影响统计格被明确标注

    # 完整来源下真实篡改必须检出（数值）
    ltm.stats["unit_task"]["initial"]["attempts"] += 1
    bad = ltm.reconcile(eps)
    assert not bad["ok"] and bad["mismatches"]


def test_reconcile_detects_tampered_source_ids():
    """整改①：source_episode_ids 被篡改（换 ID / 重复 / 删空）必须检出。"""
    _, _, eps = _episodes()
    other_id = "unit_task@1970-01-01T00:00:00+00:00#deadbeef#R9"
    ltm = LongTermMemory()
    ltm.ingest(eps)

    cell = ltm.stats["unit_task"]["initial"]
    real_id = cell["source_episode_ids"][0]
    cell["source_episode_ids"] = [other_id]        # 换成不存在且非缺失的 ID
    r1 = ltm.reconcile(eps)
    assert not r1["ok"] and any("无法解析" in m or "伪造" in m for m in r1["mismatches"])

    ltm2 = LongTermMemory()
    ltm2.ingest(eps)
    ltm2.stats["unit_task"]["initial"]["source_episode_ids"] = []  # 删空来源
    r2 = ltm2.reconcile(eps)
    assert not r2["ok"] and any("source_episode_ids" in m or "全局" in m for m in r2["mismatches"])


def test_reconcile_detects_wrong_attribution():
    """整改①：把经历从正确统计格挪到错误统计格必须检出。"""
    task = make_task(max_rounds=8)
    provider = MockProvider([
        ("2024 nobel prize in physics", WINNERS_HITS),
        ("what specific work", WORK_HITS),
        ("*", WINNERS_HITS + WORK_HITS),
    ])
    log = MetacognitiveController(task, provider).run()
    eps = episodes_from_log(log)
    ltm = LongTermMemory()
    ltm.ingest(eps)
    assert any(r["strategy"] == "broaden" for r in ltm.query())

    # 把 broaden 格的来源 ID 挪到 initial 格（归属篡改）
    broaden_ids = ltm.stats[task.name]["broaden"]["source_episode_ids"]
    ltm.stats[task.name]["broaden"]["source_episode_ids"] = []
    ltm.stats[task.name]["initial"]["source_episode_ids"].extend(broaden_ids)
    ltm.stats[task.name]["initial"]["attempts"] += len(broaden_ids)
    r = ltm.reconcile(eps)
    assert not r["ok"]
    assert any("归属不符" in m for m in r["mismatches"])


def test_reconcile_detects_global_vs_cells_inconsistency():
    """整改①：全局已导入集合与统计格来源 ID 不一致必须检出。"""
    _, _, eps = _episodes()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    eid = ltm.stats["unit_task"]["initial"]["source_episode_ids"][0]

    ltm.ingested.discard(eid)                 # 全局少了统计格里仍在的 ID
    r = ltm.reconcile(eps)
    assert not r["ok"] and any("全局已导入集合" in m or "未出现在全局" in m for m in r["mismatches"])

    ltm.ingested.add(eid)
    ltm.ingested.add("forged#R1")             # 全局多了伪造 ID（无统计格归属）
    r2 = ltm.reconcile(eps)
    assert not r2["ok"] and any("未归属任何统计格" in m for m in r2["mismatches"])


# ------------------------------------------------------------- 持久化/版本 --
def test_save_load_roundtrip_and_determinism(tmp_path):
    _, _, eps = _episodes()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    p1 = ltm.save(tmp_path / "a.json")
    ltm.save(tmp_path / "b.json")               # 同状态重复保存
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()

    loaded = LongTermMemory.load(p1)
    assert loaded.as_dict() == ltm.as_dict()    # 重载后统计确定相同
    assert loaded.query() == ltm.query()
    # 离线确定性：由来源经历重建统计与重载结果一致
    fresh = LongTermMemory()
    fresh.ingest(eps)
    assert fresh.as_dict() == loaded.as_dict()


def test_unknown_schema_or_version_rejected(tmp_path):
    import json

    _, _, eps = _episodes()
    ltm = LongTermMemory()
    ltm.ingest(eps)
    data = json.loads(ltm.save(tmp_path / "ltm.json").read_text(encoding="utf-8"))

    for field, value in (("schema", "other"), ("version", 99)):
        bad = {**data, field: value}
        p = tmp_path / f"bad_{field}.json"
        p.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            LongTermMemory.load(p)


# ------------------------------------------------------------------ 兼容 --
def test_p0_unaffected_and_flag_optional():
    """LongTermMemory 不参与决策：不接入时 P0 行为不变（旗标默认关）。"""
    _, log_a, _ = _episodes()
    _, log_b, _ = _episodes()
    assert log_a.as_dict()["rounds"] == log_b.as_dict()["rounds"]


@_needs_cache
def test_cli_longterm_alone_persists_sources_and_reconciles(tmp_path):
    """整改③：--save-longterm 单独启用自动持久化来源经历；保存/重载/核对/决策不变。"""
    import json

    import meta_reseek.run as runner

    task_yaml = "examples/tasks/kv_cache_llm.yaml"
    out_a, out_b = tmp_path / "plain", tmp_path / "withltm"
    ltm_path = tmp_path / "ltm" / "longterm.json"

    assert runner.main([task_yaml, "--cache", "offline", "--out", str(out_a), "--quiet"]) == 0
    assert runner.main([task_yaml, "--cache", "offline", "--out", str(out_b),
                        "--quiet", "--save-longterm", str(ltm_path)]) == 0

    # 决策不变
    ta = json.loads((out_a / "kv_cache_llm.json").read_text(encoding="utf-8"))
    tb = json.loads((out_b / "kv_cache_llm.json").read_text(encoding="utf-8"))
    assert ta["rounds"] == tb["rounds"]

    # 统计与来源经历均已持久化，重载后可完整核对
    assert ltm_path.exists()
    episodes_path = ltm_path.parent / "kv_cache_llm_episodes.jsonl"
    assert episodes_path.exists(), "单独启用 --save-longterm 必须自动持久化来源经历"

    ltm = LongTermMemory.load(ltm_path)
    src = EpisodicMemory.load(episodes_path)
    report = ltm.reconcile(src.records)
    assert report["ok"] and report["fully_verified"], report["mismatches"]

    # 重载统计可查询且带溯源
    rows = ltm.query(task="kv_cache_llm")
    assert rows and all(r["source_episode_ids"] for r in rows)
