"""Shared lexical utilities (no dependencies; deterministic)."""

from __future__ import annotations

import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "how", "if", "in", "into", "is", "it", "its", "of", "on",
    "or", "than", "that", "the", "their", "there", "these", "this", "to",
    "was", "were", "what", "when", "which", "who", "why", "will", "with",
    "does", "do", "did", "can", "could", "should", "would", "about",
}

WORD_RE = re.compile(r"[a-z0-9]+")


def words(term: str) -> list[str]:
    """Content words of a term/phrase, lowercase, stopwords dropped."""
    return [w for w in WORD_RE.findall(term.lower()) if len(w) > 1 and w not in STOPWORDS]


def tokenize(text: str) -> set[str]:
    """Set of content words of a free-text document (title+snippet)."""
    return set(words(text))
