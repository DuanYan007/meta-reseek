"""Unit tests for perception + evaluation."""

from meta_reseek.evidence import EvidenceStore
from meta_reseek.metacog.evaluation import evaluate
from meta_reseek.metacog.perception import perceive
from meta_reseek.search.base import SearchHit

from conftest import WINNERS_HITS, WORK_HITS, make_task


def _store_with(*hit_groups) -> EvidenceStore:
    store = EvidenceStore()
    task = make_task()
    for idx, hits in enumerate(hit_groups, start=1):
        store.ingest(hits, task=task, round_idx=idx, query_used="q", strategy="s")
    return store


def test_perception_reports_coverage_and_weakest():
    task = make_task()
    store = _store_with(WINNERS_HITS)
    snap = perceive(store, task, round_idx=2)
    assert snap.per_subq["winners"].relevant_count == 2
    assert snap.per_subq["work"].relevant_count == 0
    assert snap.weakest_subq(2) == "work"
    assert snap.coverage_score(2) == 0.5


def test_evaluate_insufficient_on_partial_coverage():
    task = make_task()
    snap = perceive(_store_with(WINNERS_HITS), task, round_idx=2)
    a = evaluate(snap, task, recent_gains=[2])
    assert a.verdict == "insufficient"
    assert a.weakest == "work"
    assert "work" in a.rationale


def test_evaluate_sufficient_when_all_covered_with_two_domains():
    task = make_task()
    store = _store_with(WINNERS_HITS, WORK_HITS)
    snap = perceive(store, task, round_idx=3)
    a = evaluate(snap, task, recent_gains=[2, 2])
    assert a.verdict == "sufficient"
    assert a.score > 0.7


def test_evaluate_sufficient_requires_two_domains():
    task = make_task()
    store = EvidenceStore()
    from conftest import SearchHit  # noqa: F401  (explicit import for clarity)

    # every hit on the SAME domain, two per sub-question
    same_domain = [
        SearchHit(WINNERS_HITS[0].title, "https://en.wikipedia.org/wiki/a", WINNERS_HITS[0].snippet),
        SearchHit(WINNERS_HITS[1].title, "https://en.wikipedia.org/wiki/b", WINNERS_HITS[1].snippet),
        SearchHit(WORK_HITS[0].title, "https://en.wikipedia.org/wiki/c", WORK_HITS[0].snippet),
        SearchHit(WORK_HITS[1].title, "https://en.wikipedia.org/wiki/d", WORK_HITS[1].snippet),
    ]
    for i, h in enumerate(same_domain, start=1):
        store.ingest([h], task=task, round_idx=i, query_used="q", strategy="s")
    snap = perceive(store, task, round_idx=3)
    assert snap.per_subq["winners"].relevant_count >= 2
    assert snap.per_subq["work"].relevant_count >= 2
    a = evaluate(snap, task, recent_gains=[2, 2])
    assert a.verdict == "insufficient"  # coverage met but single source domain


def test_evaluate_diminishing_after_stall_window():
    task = make_task()
    snap = perceive(_store_with(WINNERS_HITS), task, round_idx=5)
    a = evaluate(snap, task, recent_gains=[2, 0, 0, 0])
    assert a.verdict == "diminishing"
    assert "边际收益" in a.rationale


def test_evaluate_no_early_diminishing_stop():
    task = make_task()
    snap = perceive(_store_with(WINNERS_HITS), task, round_idx=3)
    a = evaluate(snap, task, recent_gains=[2, 0])
    assert a.verdict == "insufficient"  # round 3 is not > MIN_ROUNDS_BEFORE_STALL


def test_evaluate_diminishing_blames_broken_channel_not_strategy():
    task = make_task()
    snap = perceive(_store_with(WINNERS_HITS), task, round_idx=5)
    a = evaluate(snap, task, recent_gains=[2, 0, 0, 0], error_rounds_in_window=2)
    assert a.verdict == "diminishing"
    assert "通道故障" in a.rationale and "基础设施" in a.rationale

    b = evaluate(snap, task, recent_gains=[2, 0, 0, 0], error_rounds_in_window=0)
    assert "通道故障" not in b.rationale  # honest attribution either way
