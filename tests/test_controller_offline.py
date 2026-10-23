"""Offline end-to-end tests of the metacognitive loop (no network).

Three stop paths are exercised with a scripted mock provider:
early self-stop (sufficient), forced stop (max rounds), and
diminishing-returns stop.
"""

from __future__ import annotations

import json

from meta_reseek.metacog.controller import MetacognitiveController

from conftest import IRRELEVANT_HITS, MockProvider, WINNERS_HITS, WORK_HITS, make_task


def _queries(log) -> list[str]:
    return [
        r.action["query"].lower().strip()
        for r in log.records
        if r.action and r.action.get("query")
    ]


def test_loop_stops_early_when_sufficient():
    task = make_task(max_rounds=8)
    provider = MockProvider(
        [
            ("2024 nobel prize in physics", WINNERS_HITS),  # seed query
            ("laureates of the 2024 nobel prize", WINNERS_HITS),  # widen/variants
            ("what specific work", WORK_HITS),
            ("*", WINNERS_HITS + WORK_HITS),
        ]
    )
    log = MetacognitiveController(task, provider).run()
    decisions = [r.decision for r in log.records]
    assert decisions[-1] == "stop_sufficient"
    assert "search" in decisions
    assert len(log.records) < task.max_rounds + 1  # stopped before forced stop
    summary = log.summary()
    assert summary["final_verdict"] == "sufficient"
    # feedback must have been recorded for every search round
    search_records = [r for r in log.records if r.decision == "search"]
    assert search_records and all(r.feedback for r in search_records)
    assert any(r.feedback["effect"] == "helpful" for r in search_records)


def test_loop_never_issues_duplicate_queries():
    task = make_task(max_rounds=8)
    provider = MockProvider([("*", WINNERS_HITS + WORK_HITS)])
    log = MetacognitiveController(task, provider).run()
    qs = _queries(log)
    assert len(qs) == len(set(qs))


def test_loop_forced_stop_when_provider_never_helps():
    task = make_task(max_rounds=3)
    provider = MockProvider([("*", IRRELEVANT_HITS)])
    log = MetacognitiveController(task, provider).run()
    decisions = [r.decision for r in log.records]
    assert decisions.count("search") == 3
    assert decisions[-1] == "stop_forced"
    summary = log.summary()
    # evidence never arrived: the final check reports the gap honestly
    assert summary["final_verdict"] in {"insufficient", "diminishing"}
    assert summary["effect_counts"].get("stalled", 0) == 3


def test_loop_diminishing_stop_when_gains_vanish():
    task = make_task(max_rounds=8)
    provider = MockProvider(
        [
            ("2024 nobel prize in physics", WINNERS_HITS),  # round 1: useful
            ("*", WINNERS_HITS),  # later rounds: only duplicates arrive
        ]
    )
    log = MetacognitiveController(task, provider).run()
    decisions = [r.decision for r in log.records]
    assert decisions[-1] == "stop_diminishing"
    # and it must stop well before exhausting max_rounds
    assert len([d for d in decisions if d == "search"]) < task.max_rounds


def test_loop_diminishing_stop_blames_provider_failures():
    """Zero gain caused by a broken channel must be attributed to the channel."""
    task = make_task(max_rounds=8)

    class FlakyProvider(MockProvider):
        name = "flaky"

        def __init__(self):
            super().__init__([("2024 nobel prize in physics", WINNERS_HITS), ("*", [])])
            self.last_error = None

        def search(self, query: str, max_results: int = 5):
            hits = super().search(query, max_results)
            self.last_error = (
                "RequestError: tls handshake eof" if not hits else None
            )
            return hits

    log = MetacognitiveController(task, FlakyProvider()).run()
    assert log.records[-1].decision == "stop_diminishing"
    assert "通道故障" in log.records[-1].decision_reason
    # every zero-gain round flagged the failure in its feedback record
    failures = [r for r in log.records if r.feedback and r.feedback["provider_error"]]
    assert failures, "provider errors must be visible in the trace"


def test_trace_serializes_to_json_with_required_fields():
    task = make_task(max_rounds=3)
    provider = MockProvider([("*", WINNERS_HITS)])
    log = MetacognitiveController(task, provider).run()
    trace = json.loads(json.dumps(log.as_dict(), ensure_ascii=False))
    assert {"task", "config", "rounds", "evidence", "summary"} <= set(trace)
    added_total = sum(
        r["ingest"]["added"] for r in trace["rounds"] if r["ingest"]
    )
    assert len(trace["evidence"]) == added_total
    for ev in trace["evidence"]:
        assert ev["url"] and ev["round_added"] >= 1 and ev["relevance"]
    for record in trace["rounds"]:
        assert record["perception"] and record["evaluation"] and record["decision_reason"]
        if record["decision"] == "search":
            assert record["action"]["query"]
            assert record["ingest"] is not None
            assert record["feedback"]["effect"] in {"helpful", "neutral", "stalled"}


def test_every_search_round_has_perception_evaluation_adjustment_feedback():
    task = make_task(max_rounds=4)
    provider = MockProvider([("*", WINNERS_HITS + WORK_HITS)])
    log = MetacognitiveController(task, provider).run()
    for r in log.records:
        if r.decision == "search":
            assert r.perception["per_subq"]
            assert r.evaluation["verdict"] in {"insufficient", "sufficient", "diminishing"}
            assert r.action["strategy"] in {
                "initial",
                "target_weakest",
                "specialize",
                "broaden",
                "diversify",
            }
            assert r.feedback is not None
