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


def test_committed_summary_matches_recompute():
    committed = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    fresh = run_eval.run_all()
    # 结构性指标必须可离线重算一致（mock 全量；replay 在本机有缓存时同样一致）
    assert committed["stop_path_triggers"] == fresh["stop_path_triggers"]
    assert [r["id"] for r in committed["results"]] == [r["id"] for r in fresh["results"]]
    for c, f in zip(committed["results"], fresh["results"]):
        if c.get("class") != "mock":
            continue
        for key in ("stop_consistent", "actual_stop", "rounds_searched",
                    "queries_unique", "evidence_total", "duplicates_rejected",
                    "channel_error_rounds", "retries_total", "memory_traceable"):
            assert c[key] == f[key], (c["id"], key)


def test_summary_report_regenerates_byte_identical():
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    assert run_eval.build_report(summary) == (RESULTS / "summary.md").read_text(encoding="utf-8")


def test_pinned_overall_outcomes():
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    ok = [r for r in summary["results"] if r["status"] == "ok"]
    assert len(ok) == 12  # 本机含缓存：9 mock + 3 replay
    assert summary["stop_path_triggers"] == {
        "stop_sufficient": 9, "stop_diminishing": 2, "stop_forced": 1,
    }
    assert all(r["stop_consistent"] for r in ok)      # 停止决策与冻结预期全部一致
    assert all(r["queries_unique"] for r in ok)       # 查询去重全程成立
    assert all(r["memory_traceable"] for r in ok)     # 三层记忆溯源全程成立
    # M5/M6：通道最终失败 vs 重试恢复的区分
    m5 = next(r for r in ok if r["id"] == "M5-provider-final-failure")
    m6 = next(r for r in ok if r["id"] == "M6-retry-recovered")
    assert m5["channel_error_rounds"] == 2 and m5["attribution_mentions_channel"]
    assert m6["channel_error_rounds"] == 0 and m6["retries_total"] == 1
    # M7：伪覆盖下关键条件缺口被指标暴露
    m7 = next(r for r in ok if r["id"] == "M7-pseudo-high-coverage")
    assert m7["key_condition_gap_found"] and m7["key_condition_gaps"]["b"]
    # M8：冻结预期未达成的诊断如实记录（去重阈值局限）
    m8 = next(r for r in ok if r["id"] == "M8-duplicates-same-source")
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
