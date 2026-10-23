from meta_reseek.evidence import (
    EvidenceStore,
    normalize_url,
    relevance,
)
from meta_reseek.task import SubQuestion
from meta_reseek.textutil import tokenize

from conftest import WINNERS_HITS, hit, make_task


def test_tokenize_drops_stopwords_and_short_tokens():
    assert tokenize("The Who, and What of 2024 Physics!") == {"2024", "physics"}


def test_relevance_full_match_beats_partial():
    terms = ["Nobel Prize", "2024", "laureates"]
    full = relevance("The Nobel Prize 2024 laureates in Physics", terms)
    partial = relevance("The Nobel Prize 2025 laureates in Chemistry", terms)
    assert full == 1.0
    assert 0.0 < partial < 1.0


def test_relevance_multiword_term_needs_all_words():
    terms = ["artificial neural networks"]
    assert relevance("artificial neural networks enable learning", terms) == 1.0
    assert relevance("artificial networks", terms) == 0.0


def test_relevance_empty_terms_is_zero():
    assert relevance("anything", []) == 0.0


def test_normalize_url_strips_scheme_www_tracking_and_slash():
    assert (
        normalize_url("https://www.nobelprize.org/prizes/physics/2024/?utm_source=x")
        == "nobelprize.org/prizes/physics/2024"
    )
    assert normalize_url("https://Example.com/a/") == "example.com/a"


def test_ingest_scores_against_all_subquestions():
    store = EvidenceStore()
    task = make_task()
    report = store.ingest(
        WINNERS_HITS, task=task, round_idx=1, query_used="q", strategy="initial"
    )
    assert report.added == 2 and report.irrelevant == 0
    item = store.items[0]
    assert item.relevance["winners"] > item.relevance["work"]


def test_ingest_rejects_duplicate_urls_and_near_duplicate_titles():
    store = EvidenceStore()
    task = make_task()
    first = store.ingest(
        WINNERS_HITS, task=task, round_idx=1, query_used="q", strategy="initial"
    )
    same_again = store.ingest(
        WINNERS_HITS, task=task, round_idx=2, query_used="q2", strategy="target_weakest"
    )
    near_dup = store.ingest(
        [
            hit(  # different URL, same domain, near-identical title
                "https://en.wikipedia.org/wiki/2024_Nobel_Prize_in_Physics",
                "2024 Nobel Prizes in Physics - Wikipedia",
                "Same story retold about Hopfield and Hinton laureates.",
            )
        ],
        task=task,
        round_idx=3,
        query_used="q3",
        strategy="target_weakest",
    )
    assert first.added == 2
    assert same_again.duplicates == 2 and same_again.added == 0
    assert near_dup.duplicates == 1 and near_dup.added == 0


def test_ingest_rejects_irrelevant_hits():
    store = EvidenceStore()
    task = make_task()
    from conftest import IRRELEVANT_HITS

    report = store.ingest(
        IRRELEVANT_HITS, task=task, round_idx=1, query_used="q", strategy="initial"
    )
    assert report.added == 0 and report.irrelevant == 1


def test_subquestion_terms_deduplicate_and_merge_keywords():
    sq = SubQuestion(id="x", text="What is the Nobel Prize worth", keywords=["Nobel Prize", "money"])
    terms = sq.terms
    assert terms[0] == "nobel prize" and terms.count("nobel") == 0
    assert "money" in terms and "worth" in terms
