"""Task B offline tests: sufficiency criteria behaviour on the fixed case set.

Pins: point hits with evidence, the anti-splitting rule, snapshot verdicts,
the annotation-dispute record, and byte-identical report regeneration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

import run_sufficiency
import sufficiency_criteria as sc
from common import load

RESULTS = REPO / "experiments/p1a/results"


def _cases_by_id():
    _, cases, _ = load()
    return {c["id"]: c for c in cases}


def test_point_hits_with_evidence_on_real_cases():
    cases = _cases_by_id()
    e001 = f"{cases['e001']['title']}\n{cases['e001']['snippet']}"
    res = sc.doc_level(e001, "techniques")
    assert res["class"] == "condition_met"
    assert "P1-具体技术（名称或类别）" in res["evidence"]
    assert "GQA" in res["evidence"]["P1-具体技术（名称或类别）"]

    # CALC names determinants but no growth relation -> P1 (mechanism) missing
    calc = f"{cases['CALC-missing-why']['title']}\n{cases['CALC-missing-why']['snippet']}"
    res = sc.doc_level(calc, "cost")
    assert "P1-增长关系（机制）" in res["missing_points"]
    assert res["class"] != "condition_met"

    # gaming page: hits the magnitude point only via the bare word "VRAM"
    # (a pattern-granularity weakness, documented in the report limitations);
    # the mechanism point gates it, so it is NOT condition_met either way
    gaming = f"{cases['C-topic-cost']['title']}\n{cases['C-topic-cost']['snippet']}"
    res = sc.doc_level(gaming, "cost")
    assert res["class"] == "partial_points"
    assert "P1-增长关系（机制）" in res["missing_points"]
    assert res["class"] != "condition_met"


def test_anti_splitting_rule_on_synthetic_docs():
    """Points covered by two different docs, none covering all -> v1
    sufficient, v2 (anti-splitting) insufficient."""
    docs = [
        {"id": "d1", "domain": "a.com", "text": "the cache grows linearly with context length"},
        {"id": "d2", "domain": "b.com", "text": "the cache can consume 72 GB of VRAM"},
    ]
    v1 = sc.snapshot_level(docs, "cost", require_condition_met_doc=False)
    v2 = sc.snapshot_level(docs, "cost", require_condition_met_doc=True)
    assert v1["sufficient"] is True          # points + 2 domains
    assert v2["sufficient"] is False         # no single doc covers both points
    assert "防跨文档碎片拼接" in v2["reason"] or "拼接" in v2["reason"]


def test_snapshot_verdicts_and_annotation_dispute_record():
    task, cases, snapshots = load()
    results = run_sufficiency.compute(task, cases, snapshots)
    by_id = {r["snapshot"]: r for r in results["v2_antisplit"]}

    # S2: topic/partial coverage does not fool the criteria -> continue (fixes
    # the lexical arm's wrong stop on the same snapshot)
    s2 = by_id["S2-pseudo-coverage-wrong-stop"]
    assert s2["criteria_stop_suggestion"] == "continue"
    assert s2["stop_decision_correct"] is True
    assert "P1-增长关系（机制）" in s2["per_subq"]["cost"]["missing_points"]

    # S3: criteria says techniques sufficient (e001 full snippet evidence);
    # annotation (drafted on a truncated view) says insufficient and now
    # carries an uncertainty record — a dispute for human review, not a silent fix
    s3 = by_id["S3-real-after-round2"]
    tech = s3["per_subq"]["techniques"]
    assert tech["sufficient"] is True
    assert tech["condition_met_docs"] == ["e001"]
    assert s3["stop_decision_correct"] is False  # honest mismatch, disputed
    spec = {s["id"]: s for s in snapshots}["S3-real-after-round2"]
    assert spec["sufficiency"]["techniques"].get("uncertain") is True

    # pinned overall accuracy of the three arms on the five snapshots
    def acc(rows):
        return sum(1 for r in rows if r["stop_decision_correct"])
    assert acc(results["v1_points_domains"]) == 4
    assert acc(results["v2_antisplit"]) == 4  # anti-splitting changes nothing here
    lex = json.loads((RESULTS / "lexical_baseline.json").read_text(encoding="utf-8"))
    sem = json.loads((RESULTS / "semantic_comparison.json").read_text(encoding="utf-8"))
    assert acc(lex["snapshots"]) == 4
    assert acc(sem["snapshots"]) == 2  # semantic @0.5


def test_sufficiency_report_regenerates_byte_identical():
    task, cases, snapshots = load()
    lex = json.loads((RESULTS / "lexical_baseline.json").read_text(encoding="utf-8"))
    sem = json.loads((RESULTS / "semantic_comparison.json").read_text(encoding="utf-8"))
    results = json.loads((RESULTS / "sufficiency_comparison.json").read_text(encoding="utf-8"))
    regenerated = run_sufficiency.build_report(task, cases, snapshots, results, lex, sem)
    committed = (RESULTS / "sufficiency_report.md").read_text(encoding="utf-8")
    assert regenerated == committed, (
        "committed sufficiency_report.md is stale: re-run experiments/p1a/run_sufficiency.py"
    )
