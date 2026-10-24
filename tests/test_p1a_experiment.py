"""Offline tests for the P1-a experiment assets (no model, no network).

- cases.json schema: provenance, complete candidate annotations with basis,
  snapshots referencing existing cases;
- lexical baseline is deterministic and its known real errors are pinned, so
  a future regression (or silent annotation drift) is caught;
- snapshot S2's wrong-stop behaviour (the finding the round is built on)
  must reproduce offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "experiments/p1a"))

import json

from common import (ABS_THRESHOLD, accept_rule, compare_with_annotation,
                    doc_level_report, lexical_scores, load,
                    snapshot_verdict)

SUBQ_IDS = {"definition", "cost", "techniques"}


def _load():
    return load()


def test_case_set_schema_and_provenance():
    task, cases, snapshots = _load()
    assert 12 <= len(cases) <= 20
    ids = set()
    levels = {"irrelevant", "topic_only", "partial", "sufficient_support"}
    for case in cases:
        assert case["id"] not in ids
        ids.add(case["id"])
        assert case["title"] and case["snippet"] and case["domain"]
        assert case["source"]  # provenance is mandatory
        assert "标题与摘要" in case["source"] if case["intent"] == "real" else True
        assert set(case["doc_annotation"]) == SUBQ_IDS
        for ann in case["doc_annotation"].values():
            assert ann["level"] in levels and ann["basis"]
    real = [c for c in cases if c["intent"] == "real"]
    constructed = [c for c in cases if c["intent"] != "real"]
    assert len(real) >= 12 and len(constructed) >= 4
    # 同源去重：同一论文双版本只保留一条
    urls = [c["url"] for c in real]
    assert len({u.split("arxiv.org")[1].split("v")[0].rstrip("0123456789") for u in urls if "arxiv" in u}) == \
           len([u for u in urls if "arxiv" in u])
    for snap in snapshots:
        assert snap["members"], snap["id"]
        for m in snap["members"]:
            assert m in ids
        assert set(snap["sufficiency"]) == SUBQ_IDS
        for v in snap["sufficiency"].values():
            assert isinstance(v["sufficient"], bool) and v["basis"]


def test_candidate_annotation_status_and_scale_declared():
    data = json.loads((REPO / "experiments/p1a/cases.json").read_text(encoding="utf-8"))
    assert "CANDIDATE" in data["annotation_status"]  # never claimed as verified gold
    assert set(data["annotation_scale"]) == {
        "irrelevant", "topic_only", "partial", "sufficient_support",
    }
    assert data["revision_log"], "revision log is mandatory after the review rework"
    assert "标题与摘要" in data["evidence_scope"]  # evidence scope wording fixed


def test_lexical_baseline_is_deterministic_and_pinned():
    task, cases, snapshots = _load()
    scores1 = lexical_scores(task, cases)
    scores2 = lexical_scores(task, cases)
    assert scores1 == scores2  # pure function, offline

    accepted = {
        cid: accept_rule({sid: v["score"] for sid, v in per.items()}, ABS_THRESHOLD)
        for cid, per in scores1.items()
    }
    confusion, errors, _, accepted_levels = doc_level_report(cases, accepted)
    # pinned after the 2026-10-24 rework (4-level annotations, e012 dedup)
    assert confusion["FN"] == 7 and confusion["FP"] == 8
    err_pairs = {(e["case"], e["subq"]) for e in errors}
    assert ("e014", "techniques") in err_pairs      # real synonym miss (compression)
    assert ("C-topic-cost", "cost") in err_pairs    # constructed topic-overlap FP
    assert ("e011", "definition") in err_pairs      # real cross-subq misattribution
    assert ("e011", "techniques") in err_pairs      # same cause, FN on the right subq
    real_def_fps = {c for c, s in err_pairs if s == "definition" and c.startswith("e0")}
    assert len(real_def_fps) == 6  # e012 deduped: was 7
    # accepted-but-thin evidence: the 4-level scale makes pseudo-acceptance visible
    assert accepted_levels.get("topic_only") == 8
    assert accepted_levels.get("partial") == 6
    assert accepted_levels.get("sufficient_support") == 11


def test_snapshot_s2_reproduces_wrong_stop_offline():
    task, cases, snapshots = _load()
    spec = {s["id"]: s for s in snapshots}["S2-pseudo-coverage-wrong-stop"]
    scores = lexical_scores(task, cases)
    accepted = {
        cid: accept_rule({sid: v["score"] for sid, v in per.items()}, ABS_THRESHOLD)
        for cid, per in scores.items()
    }
    cases_by_id = {c["id"]: c for c in cases}
    snap, assessment = snapshot_verdict(task, cases_by_id, spec["members"], accepted)
    row = compare_with_annotation(task, snap, assessment, spec)
    assert assessment.verdict == "sufficient"        # evaluator says stop
    assert row["annotation_stop_should_be"] == "continue"  # no mechanism doc for cost
    assert row["stop_decision_correct"] is False     # the pinned finding

    # while the real mid-run control snapshot S3 must stay a correct continue
    spec3 = {s["id"]: s for s in snapshots}["S3-real-after-round2"]
    snap3, a3 = snapshot_verdict(task, cases_by_id, spec3["members"], accepted)
    row3 = compare_with_annotation(task, snap3, a3, spec3)
    assert row3["stop_decision_correct"] is True
