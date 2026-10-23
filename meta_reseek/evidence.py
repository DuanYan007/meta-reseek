"""Evidence store: ingest search hits, score relevance, deduplicate."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse

from .search.base import SearchHit
from .task import SubQuestion, TaskSpec
from .textutil import tokenize, words

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref_", "yclid", "mc_", "igshid")


def relevance(doc_text: str, terms: list[str], common: set[str] | None = None) -> float:
    """Share of scoring-term weight present in the document (title+snippet).

    - A multi-word term counts only when all its words appear, and weighs
      more because it is more specific.
    - Terms shared by several sub-questions (``common``) are down-weighted
      x0.25: they say "same topic", not "answers THIS sub-question".
    Returns 0..1, deterministic.
    """
    if not terms:
        return 0.0
    doc_tokens = tokenize(doc_text)
    common = common or set()
    total_w = 0.0
    hit_w = 0.0
    for term in terms:
        ws = words(term)
        if not ws:
            continue
        weight = (1.0 + 0.5 * (len(ws) - 1)) * (0.25 if term in common else 1.0)
        total_w += weight
        if all(w in doc_tokens for w in ws):
            hit_w += weight
    return hit_w / total_w if total_w else 0.0


def normalize_url(url: str) -> str:
    """Canonical form for duplicate detection: no scheme/www, no tracking
    query params, no trailing slash."""
    p = urlparse(url.strip())
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+$", "", p.path or "")
    keep = [
        (k, v)
        for k, v in parse_qsl(p.query or "", keep_blank_values=True)
        if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    canonical = f"{host}{path}"
    if keep:
        canonical += f"?{urlencode(keep)}"
    return canonical


def _title_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class EvidenceItem:
    eid: str
    url: str
    domain: str
    title: str
    snippet: str
    round_added: int
    query_used: str
    strategy: str
    relevance: dict[str, float] = field(default_factory=dict)  # subq_id -> score

    @property
    def best_subq(self) -> tuple[str, float] | None:
        if not self.relevance:
            return None
        subq_id, score = max(self.relevance.items(), key=lambda kv: kv[1])
        return (subq_id, score)


@dataclass
class IngestReport:
    candidates: int = 0
    added: int = 0
    duplicates: int = 0
    irrelevant: int = 0

    def as_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "added": self.added,
            "duplicates": self.duplicates,
            "irrelevant": self.irrelevant,
        }


class EvidenceStore:
    """Holds accepted evidence; rejects duplicates and off-topic hits."""

    MIN_RELEVANCE = 0.15       # below this max score a hit is off-topic
    RELATIVE_MARGIN = 0.6      # a doc counts for subq s only if its score for s
                              # reaches this share of its best subq score

    def __init__(self) -> None:
        self.items: list[EvidenceItem] = []
        self._by_url: dict[str, EvidenceItem] = {}
        self._titles: list[set[str]] = []
        self._domains: list[str] = []

    # -- queries ---------------------------------------------------------

    def relevant(self, subq: SubQuestion, min_score: float | None = None) -> list[EvidenceItem]:
        """Items that genuinely answer this sub-question: absolute threshold
        plus relative margin against the item's best-matching sub-question."""
        threshold = self.MIN_RELEVANCE if min_score is None else min_score
        out = []
        for it in self.items:
            score = it.relevance.get(subq.id, 0.0)
            best = max(it.relevance.values(), default=0.0)
            if score >= threshold and score >= self.RELATIVE_MARGIN * best:
                out.append(it)
        return out

    def domain_count(self) -> int:
        return len(set(self._domains))

    def items_from_round(self, round_idx: int) -> list[EvidenceItem]:
        return [it for it in self.items if it.round_added == round_idx]

    # -- ingestion -------------------------------------------------------

    def ingest(
        self,
        hits: list[SearchHit],
        *,
        task: TaskSpec,
        round_idx: int,
        query_used: str,
        strategy: str,
    ) -> IngestReport:
        report = IngestReport(candidates=len(hits))
        for hit in hits:
            norm = normalize_url(hit.url)
            if not norm or norm in self._by_url:
                report.duplicates += 1
                continue
            title_tokens = tokenize(hit.title)
            domain = (urlparse(hit.url).netloc or "").lower().removeprefix("www.")
            near_dup = any(
                _title_similarity(title_tokens, prev) >= 0.8 and domain == prev_domain
                for prev, prev_domain in zip(self._titles, self._domains)
            )
            if near_dup:
                report.duplicates += 1
                continue
            rel = {
                sq.id: relevance(f"{hit.title}\n{hit.snippet}", sq.terms, task.common_terms)
                for sq in task.sub_questions
            }
            if max(rel.values(), default=0.0) < self.MIN_RELEVANCE:
                report.irrelevant += 1
                continue
            item = EvidenceItem(
                eid=f"e{len(self.items) + 1:03d}",
                url=hit.url,
                domain=domain,
                title=hit.title,
                snippet=hit.snippet,
                round_added=round_idx,
                query_used=query_used,
                strategy=strategy,
                relevance=rel,
            )
            self.items.append(item)
            self._by_url[norm] = item
            self._titles.append(title_tokens)
            self._domains.append(domain)
            report.added += 1
        return report
