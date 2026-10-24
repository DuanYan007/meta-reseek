"""Task 3 offline tests: frozen-rule validation outcomes are pinned so that
any change to the frozen criteria (or the fresh annotations) must surface
here. All offline; the frozen module is imported, never modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

import run_freeze_validation
import sufficiency_criteria as sc
from common import load

RESULTS = REPO / "experiments/p1a/results"


def test_frozen_criteria_shape_unchanged():
    # 冻结核心的结构锚点：子问题与要点集被改动时立即暴露
    assert set(sc.CRITERIA) == {"definition", "cost", "techniques"}
    assert list(sc.CRITERIA["definition"]) == ["P1-缓存对象", "P2-机制与目的", "P3-场景"]
    assert list(sc.CRITERIA["cost"]) == ["P1-增长关系（机制）", "P2-量级与占用"]
    assert list(sc.CRITERIA["techniques"]) == ["P1-具体技术（名称或类别）", "P2-作用方式（缩减/管理）"]


def test_fresh_kv_validation_pinned():
    task, cases, snapshots = load()
    val = run_freeze_validation.validate_fresh_kv()
    n = val["relevance_agreement"]["ok"] + val["relevance_agreement"]["bad"]
    assert n == 12  # 4 independent docs (f03/f05 excluded as same-source) x 3 subqs
    assert val["relevance_agreement"] == {"ok": 8, "bad": 4}
    assert val["condition_met_agreement"] == {"ok": 11, "bad": 1}
    # the remaining known degradation: nominalized "reduction" (no "reduce" substring)
    rows = {r["doc"] + "/" + r["subq"]: r for r in val["rows"]}
    assert rows["f06/techniques"]["pred_class"] != "condition_met"
    # reworked annotation standard (整改②): claim-level titles downgraded to partial + uncertain
    assert rows["f02/cost"]["gold_level"] == "partial" and rows["f02/cost"]["uncertain"]
    assert rows["f04/techniques"]["gold_level"] == "partial" and rows["f04/techniques"]["uncertain"]
    # all four relevance misses are claim-level definition pages (bare-word P1 hit)
    assert {r["subq"] for r in val["rows"] if not r["relevance_agree"]} == {"definition"}


def test_fresh_kv_provenance_and_exclusions():
    import criteria_audit as audit
    for d in audit.FRESH_KV:
        assert d.get("url") and d.get("query") and d.get("cache_key")
        assert isinstance(d.get("verifiable"), bool)
    val = run_freeze_validation.validate_fresh_kv()
    excluded = {e["doc"]: e["reason"] for e in val["excluded"]}
    # 整改①: f03 is the SAME PAPER as old case e011 (arXiv 2603.20397 pdf/html),
    # f05 is the same paper as f04 (ResearchGate/IEEE portals) — neither counts
    # as independent new evidence
    assert "e011" in excluded["f03"] and "arXiv 2603.20397" in excluded["f03"]
    assert excluded["f05"].startswith("与新鲜集内条目同源")
    assert set(excluded) == {"f03", "f05"}


def test_fresh_task_eco_collision_trap_pinned():
    val = run_freeze_validation.validate_fresh_task()
    assert val["relevance_agreement"] == {"ok": 20, "bad": 10}
    trap = {t["doc"]: t["all_covered"] for t in val["eco_collision_trap"]}
    # biology page n14 ("community ecology" + "ecosystem") hits ALL ecosystem
    # points of the pre-registered new-task criteria -> false condition_met
    assert trap == {"n14": True, "n15": False, "n17": False}


def test_sensitivity_both_annotation_variants_pinned():
    task, cases, snapshots = load()
    sens = run_freeze_validation.sensitivity(task, cases, snapshots)
    a = sens["A-原标注"]["accuracy"]
    b = sens["B-替代标注(e001 佐证下 techniques 充分)"]["accuracy"]
    # annotation-dependent conclusion, reported honestly:
    assert a == {"lexical": 4, "semantic": 2, "criteria": 4}
    assert b == {"lexical": 3, "semantic": 3, "criteria": 5}


def test_disputed_snapshot_annotations_are_flagged():
    data = json.loads((REPO / "experiments/p1a/cases.json").read_text(encoding="utf-8"))
    snaps = {s["id"]: s for s in data["snapshots"]}
    flagged = [sid for sid in ("S1-homogeneous-definition", "S3-real-after-round2",
                               "S5-missing-condition")
               if snaps[sid]["sufficiency"]["techniques"].get("uncertain")]
    assert len(flagged) == 3  # all three disputes carry uncertainty records


def test_freeze_report_regenerates_byte_identical():
    task, cases, snapshots = load()
    data = json.loads((RESULTS / "freeze_validation.json").read_text(encoding="utf-8"))
    regenerated = run_freeze_validation.build_report(
        data["fresh_kv"], data["fresh_task"], data["sensitivity"], data["layered"])
    committed = (RESULTS / "freeze_validation.md").read_text(encoding="utf-8")
    assert regenerated == committed, (
        "committed freeze_validation.md is stale: re-run experiments/p1a/run_freeze_validation.py"
    )
