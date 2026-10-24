"""P1-c evaluation suite tests (offline; frozen-spec discipline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1c"))

import run_eval

RESULTS = REPO / "experiments/p1c/results"
SPEC = json.loads((REPO / "experiments/p1c/eval_tasks.json").read_text(encoding="utf-8"))

REQUIRED_CONDITIONS = {
    "sufficient_evidence", "strategy_adjustment", "diminishing_returns",
    "forced_max_rounds", "provider_final_failure", "provider_retry_recovered",
    "duplicate_and_pseudo_evidence", "key_condition_missing_high_coverage",
    "cross_domain_collision",
}


def test_frozen_spec_schema_and_coverage():
    scenarios = SPEC["scenarios"]
    assert len(scenarios) >= 10
    ids = [s["id"] for s in scenarios]
    assert len(ids) == len(set(ids))
    covered = set()
    for s in scenarios:
        assert s["class"] in {"mock", "cache-replay"}
        assert s["expected_stop"] in {"stop_sufficient", "stop_diminishing", "stop_forced"}
        assert s["conditions"] and s["purpose"]
        covered.update(s["conditions"])
        if s["class"] == "mock":
            assert s["script"] and s["task"]["sub_questions"]
    assert REQUIRED_CONDITIONS <= covered  # 八类条件全覆盖
    # 类别分离声明存在
    assert set(SPEC["classes"]) == {"mock", "cache-replay"}


def test_eval_deterministic_for_mock_class():
    a = run_eval.run_all()
    b = run_eval.run_all()
    ra = [r for r in a["results"] if r.get("class") == "mock"]
    rb = [r for r in b["results"] if r.get("class") == "mock"]
    assert ra == rb  # mock 类完全确定性


def _cache_present() -> bool:
    cache = REPO / "artifacts/cache"
    return cache.exists() and bool(list(cache.glob("*.json")))


def test_committed_summary_matches_recompute():
    """已提交的 12 场景结果作为历史评测产物保留；mock 类在任意环境可精确
    重算一致；replay 类在有缓存环境可复算一致，无缓存环境标记 skipped
    （不与历史产物冲突，也不把跳过统计为成功）。"""
    committed = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    fresh = run_eval.run_all()
    assert [r["id"] for r in committed["results"]] == [r["id"] for r in fresh["results"]]
    for c, f in zip(committed["results"], fresh["results"]):
        if c.get("class") == "mock":
            for key in ("stop_consistent", "actual_stop", "rounds_searched",
                        "queries_unique", "evidence_total", "duplicates_rejected",
                        "channel_error_rounds", "retries_total", "memory_traceable"):
                assert c[key] == f[key], (c["id"], key)
            # 仅声明 key_conditions 的场景携带跨领域诊断标记
            assert c.get("key_condition_cross_domain") == f.get("key_condition_cross_domain"), c["id"]
        else:
            if _cache_present():
                assert f["status"] == "ok"
                assert c["actual_stop"] == f["actual_stop"]
            else:
                assert f["status"] == "skipped-no-cache"


def test_summary_report_regenerates_byte_identical():
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    assert run_eval.build_report(summary) == (RESULTS / "summary.md").read_text(encoding="utf-8")


def test_pinned_overall_outcomes():
    """钉死的是**已提交的历史评测产物**（有缓存环境生成：12 场景全部 ok）；
    无缓存环境的当前行为（9 ok + 3 skipped、触发 6/2/1）由
    test_replay_scenarios_skip_gracefully_without_cache 与 recompute 测试覆盖。"""
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    ok = [r for r in summary["results"] if r["status"] == "ok"]
    mock_ok = [r for r in ok if r["class"] == "mock"]
    replay_ok = [r for r in ok if r["class"] == "cache-replay"]
    assert len(mock_ok) == 9 and len(replay_ok) == 3  # 历史产物：9 mock + 3 replay 全 ok
    assert summary["stop_path_triggers"] == {
        "stop_sufficient": 9, "stop_diminishing": 2, "stop_forced": 1,
    }
    assert all(r["stop_consistent"] for r in ok)
    assert all(r["queries_unique"] for r in ok)
    assert all(r["memory_traceable"] for r in ok)
    # M5/M6：通道最终失败 vs 重试恢复的区分
    m5 = next(r for r in mock_ok if r["id"] == "M5-provider-final-failure")
    m6 = next(r for r in mock_ok if r["id"] == "M6-retry-recovered")
    assert m5["channel_error_rounds"] == 2 and m5["attribution_mentions_channel"]
    assert m6["channel_error_rounds"] == 0 and m6["retries_total"] == 1
    # M4：离题拒绝 = 3（1 条离题命中 × 3 轮）
    m4 = next(r for r in mock_ok if r["id"] == "M4-forced")
    assert m4["irrelevant_rejected"] == 3
    # M7：伪覆盖下关键条件缺口被指标暴露，且明确标注为跨领域候选诊断
    m7 = next(r for r in mock_ok if r["id"] == "M7-pseudo-high-coverage")
    assert m7["key_condition_gap_found"] and m7["key_condition_gaps"]["b"]
    assert m7["key_condition_cross_domain"] is True
    # M8：冻结预期未达成的诊断如实记录（去重阈值局限）
    m8 = next(r for r in mock_ok if r["id"] == "M8-duplicates-same-source")
    assert m8["duplicates_consistent"] is False


def test_replay_scenarios_skip_gracefully_without_cache(tmp_path):
    summary = run_eval.run_all(cache_dir=tmp_path)  # 空缓存目录
    replay = [r for r in summary["results"] if r["class"] == "cache-replay"]
    assert len(replay) == 3
    assert all(r["status"] == "skipped-no-cache" for r in replay)
    mock = [r for r in summary["results"] if r["class"] == "mock"]
    assert len(mock) == 9 and all(r["status"] == "ok" for r in mock)
    # 缓存缺失不参与触发统计
    assert summary["stop_path_triggers"] == {
        "stop_sufficient": 6, "stop_diminishing": 2, "stop_forced": 1,
    }
