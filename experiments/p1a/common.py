"""Shared logic for the P1-a experiment arms (lexical baseline / semantic).

Both arms share: the case set, the accept-rule SHAPE (absolute threshold +
relative margin against the best sub-question), and the snapshot-level
sufficiency evaluation (the production `evaluate()` on a synthesized
Snapshot), so differences come from the *scores*, not the procedure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from meta_reseek.evidence import EvidenceStore  # noqa: E402
from meta_reseek.metacog.evaluation import evaluate  # noqa: E402
from meta_reseek.metacog.perception import Snapshot, SubqView  # noqa: E402
from meta_reseek.task import TaskSpec  # noqa: E402
from meta_reseek.textutil import tokenize, words  # noqa: E402

ABS_THRESHOLD = EvidenceStore.MIN_RELEVANCE   # 0.15 for lexical; semantic uses its own
REL_MARGIN = EvidenceStore.RELATIVE_MARGIN    # 0.6


def load(task_rel="examples/tasks/kv_cache_llm.yaml"):
    spec = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    task = TaskSpec.from_yaml(REPO / task_rel)
    return task, spec["cases"], spec["snapshots"]


# -- lexical arm -----------------------------------------------------------

def lexical_scores(task: TaskSpec, cases: list[dict]):
    """Production score + term-level explanation for cause analysis."""
    from meta_reseek.evidence import relevance

    out = {}
    for case in cases:
        text = f"{case['title']}\n{case['snippet']}"
        doc_tokens = tokenize(text)
        per_subq = {}
        for sq in task.sub_questions:
            score = relevance(text, sq.terms, task.common_terms)
            matched, missing = [], []
            for term in sq.terms:
                ws = words(term)
                if not ws:
                    continue
                hit = all(w in doc_tokens for w in ws)
                (matched if hit else missing).append(term)
            per_subq[sq.id] = {"score": score, "matched": matched, "missing": missing}
        out[case["id"]] = per_subq
    return out


# -- shared accept rule ------------------------------------------------------

def accept_rule(scores: dict[str, float], abs_threshold: float) -> dict[str, bool]:
    best = max(scores.values(), default=0.0)
    return {
        sid: s >= abs_threshold and s >= REL_MARGIN * best
        for sid, s in scores.items()
    }


# -- snapshot-level sufficiency ----------------------------------------------

def snapshot_verdict(task: TaskSpec, cases_by_id, members: list[str],
                     accepted: dict[str, dict[str, bool]]):
    """Run the production evaluator over a fixed evidence snapshot."""
    k = task.min_relevant_per_subq
    per_subq, domains = {}, set()
    for sq in task.sub_questions:
        ids = [cid for cid in members if accepted[cid].get(sq.id)]
        for cid in ids:
            domains.add(cases_by_id[cid]["domain"])
        per_subq[sq.id] = SubqView(
            id=sq.id, text=sq.text, relevant_count=len(ids), best_relevance=1.0
        )
    snap = Snapshot(
        round_idx=2,  # mid-run: only sufficient/insufficient verdicts apply
        total_items=len(members),
        per_subq=per_subq,
        domain_count=len(domains),
    )
    assessment = evaluate(snap, task, recent_gains=[1, 1], error_rounds_in_window=0)
    return snap, assessment


def compare_with_annotation(task: TaskSpec, snap: Snapshot, assessment, snapshot: dict):
    """Per-subq coverage verdict vs candidate sufficiency annotation."""
    k = task.min_relevant_per_subq
    subq_rows = {}
    for sq in task.sub_questions:
        ann = snapshot["sufficiency"][sq.id]
        covered = snap.per_subq[sq.id].relevant_count >= k
        subq_rows[sq.id] = {
            "accepted_count": snap.per_subq[sq.id].relevant_count,
            "arm_says_covered": covered,
            "annotation_sufficient": ann["sufficient"],
            "match": covered == ann["sufficient"],
            "annotation_basis": ann["basis"],
        }
    annotation_all_sufficient = all(r["annotation_sufficient"] for r in subq_rows.values())
    arm_stops = assessment.verdict == "sufficient"
    return {
        "snapshot": snapshot["id"],
        "purpose": snapshot["purpose"],
        "arm_verdict": assessment.verdict,
        "arm_score": round(assessment.score, 3),
        "arm_stop_suggestion": "stop" if arm_stops else "continue",
        "annotation_stop_should_be": "stop" if annotation_all_sufficient else "continue",
        "stop_decision_correct": arm_stops == annotation_all_sufficient,
        "per_subq": subq_rows,
    }


# -- doc-level scoring vs annotation -----------------------------------------

RELEVANT_LEVELS = {"partial", "sufficient_support"}  # 二值相关性切点：部分回答及以上算相关
SCALE_ORDER = ["irrelevant", "topic_only", "partial", "sufficient_support"]


def doc_level_report(cases, accepted: dict[str, dict[str, bool]]):
    """Confusion at the relevance cut (gold = level in RELEVANT_LEVELS), plus
    the gold-level distribution of ARM-ACCEPTED pairs (how deep below
    'sufficient_support' the accepted evidence actually sits)."""
    confusion = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    errors, corrects = [], []
    accepted_gold_levels: dict[str, int] = {}
    for case in cases:
        for sid, ann in case["doc_annotation"].items():
            gold = ann["level"] in RELEVANT_LEVELS
            pred = accepted[case["id"]].get(sid, False)
            outcome = ("TP" if gold else "FP") if pred else ("FN" if gold else "TN")
            confusion[outcome] += 1
            if pred:
                accepted_gold_levels[ann["level"]] = (
                    accepted_gold_levels.get(ann["level"], 0) + 1
                )
            row = {
                "case": case["id"], "source": case["source"], "intent": case["intent"],
                "subq": sid, "gold_level": ann["level"], "gold_relevant": gold,
                "pred": pred, "annotation_basis": ann["basis"], "title": case["title"],
            }
            (errors if outcome in {"FP", "FN"} else corrects).append(row)
    return confusion, errors, corrects, accepted_gold_levels
