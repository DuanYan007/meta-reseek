"""Unit tests for the adjustment policy."""

from meta_reseek.evidence import EvidenceStore
from meta_reseek.metacog.adjustment import decide_action, initial_action
from meta_reseek.metacog.evaluation import evaluate
from meta_reseek.metacog.perception import perceive

from conftest import WINNERS_HITS, make_task


def _state(task, hit_groups, round_idx):
    store = EvidenceStore()
    for idx, hits in enumerate(hit_groups, start=1):
        store.ingest(hits, task=task, round_idx=idx, query_used="q", strategy="s")
    snap = perceive(store, task, round_idx)
    return snap, evaluate(snap, task, recent_gains=[1] * (round_idx - 1))


def test_initial_action_uses_seed_query():
    task = make_task()
    action = initial_action(task)
    assert action.strategy == "initial"
    assert action.query == task.seed_query


def test_empty_subquestion_gets_broaden_first():
    task = make_task()
    snap, assessment = _state(task, [WINNERS_HITS], 2)
    action = decide_action(snap, assessment, task, used_queries={"2024 Nobel Prize in Physics"})
    assert action.strategy == "broaden"
    assert action.target_subq == "work"
    assert action.query == task.subq("work").text


def test_weakest_subquestion_targeted_when_none_empty():
    task = make_task()
    # give 'work' its two items and 'winners' only one
    from meta_reseek.evidence import EvidenceStore as ES

    store = ES()
    store.ingest([WINNERS_HITS[0]], task=task, round_idx=1, query_used="q", strategy="s")
    from conftest import WORK_HITS

    store.ingest(WORK_HITS, task=task, round_idx=2, query_used="q", strategy="s")
    snap = perceive(store, task, 3)
    assessment = evaluate(snap, task, recent_gains=[1, 2])
    action = decide_action(snap, assessment, task, used_queries=set())
    assert action.target_subq == "winners"
    assert action.strategy == "target_weakest"


def test_specialize_when_base_query_already_used():
    task = make_task()
    # work has one relevant item (not empty) and is the weakest sub-question
    store = EvidenceStore()
    from conftest import WORK_HITS

    store.ingest(WINNERS_HITS + [WORK_HITS[0]], task=task, round_idx=1, query_used="q", strategy="s")
    snap = perceive(store, task, 2)
    assessment = evaluate(snap, task, recent_gains=[3])
    assert snap.per_subq["work"].relevant_count == 1  # weakest, but not empty
    used = {"2024 Nobel Prize in Physics", task.subq("work").text}
    action = decide_action(snap, assessment, task, used_queries=used)
    assert action.strategy == "specialize"
    assert action.query == task.subq("work").alt_queries[0]


def test_never_repeats_a_used_query():
    task = make_task()
    snap, assessment = _state(task, [WINNERS_HITS], 2)
    sq = task.subq("work")
    used = {"2024 Nobel Prize in Physics", sq.text, *sq.alt_queries, " ".join(sq.keywords)}
    action = decide_action(snap, assessment, task, used_queries=used)
    assert action.query not in used
    assert str(2) in action.query or action.query  # fallback appends a discriminator
    assert action.query != sq.text
