"""Automatic consistency checks (task A, item 4): the committed experiment
reports must be exactly what the data regenerates, and the accepted-level
distributions must be internally consistent. All offline.

If annotations change without re-running the experiments (or a report is
hand-edited), these tests fail — docs and data cannot silently drift apart.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

import run_baseline
import run_semantic
from common import load

RESULTS = REPO / "experiments/p1a/results"


def _committed(name):
    return (RESULTS / name).read_text(encoding="utf-8")


def _committed_json(name):
    return json.loads(_committed(name))


def test_lexical_report_regenerates_byte_identical():
    task, cases, snapshots = load()
    (scores, accepted, confusion, errors,
     corrects, accepted_levels, snap_rows) = run_baseline.compute(task, cases, snapshots)
    regenerated = run_baseline.build_report(
        task, cases, snapshots, scores, confusion, errors, accepted_levels, snap_rows
    )
    assert regenerated == _committed("report_node1.md"), (
        "committed report_node1.md is stale: re-run experiments/p1a/run_baseline.py"
    )


def test_semantic_report_regenerates_byte_identical():
    task, cases, snapshots = load()
    lex = _committed_json("lexical_baseline.json")
    results = _committed_json("semantic_comparison.json")
    regenerated = run_semantic.build_report(task, cases, snapshots, results, lex)
    assert regenerated == _committed("report.md"), (
        "committed report.md is stale: re-run experiments/p1a/run_semantic.py"
    )


def test_accepted_level_distributions_are_conserved():
    for name in ("lexical_baseline.json", "semantic_comparison.json"):
        data = _committed_json(name)
        sources = [data] if "confusion" in data else []
        if "by_threshold" in data:
            sources += [data["by_threshold"][t] for t in data["by_threshold"]]
        for entry in sources:
            conf = entry["confusion"]
            dist = entry["accepted_gold_level_distribution"]
            assert sum(dist.values()) == conf["TP"] + conf["FP"], (name, conf)
            assert set(dist) <= {"irrelevant", "topic_only", "partial", "sufficient_support"}


def test_committed_stats_match_case_set():
    """The n_cases / n_pairs recorded in results equal the current cases.json."""
    task, cases, snapshots = load()
    data = _committed_json("lexical_baseline.json")
    assert data["n_cases"] == len(cases)
    assert data["n_pairs"] == sum(len(c["doc_annotation"]) for c in cases)
    for snap_spec, row in zip(snapshots, data["snapshots"]):
        assert row["snapshot"] == snap_spec["id"]  # snapshot order/ids in sync


def test_uncertain_annotations_are_declared_and_counted():
    data = json.loads((REPO / "experiments/p1a/cases.json").read_text(encoding="utf-8"))
    uncertain = [
        (c["id"], sid)
        for c in data["cases"]
        for sid, ann in c["doc_annotation"].items()
        if ann.get("uncertain")
    ]
    assert len(uncertain) == 3, "disputed labels must carry uncertainty records"
    assert set(uncertain) == {("e003", "cost"), ("E-jargon-cost", "definition"),
                              ("CALC-missing-why", "cost")}
    report = _committed("report_node1.md")
    assert "标注不确定性记录" in report  # surfaced in the generated report
