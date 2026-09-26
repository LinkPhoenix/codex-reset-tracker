from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern

from .accounts import account_group_for_handle
from .config import MatchingConfig
from .models import TweetMatch, TweetRecord


@dataclass(frozen=True)
class CompiledPattern:
    raw: str
    pattern: Pattern[str]


class RegexMatcher:
    def __init__(self, config: MatchingConfig):
        flags = 0 if config.case_sensitive else re.IGNORECASE
        self._require_all = config.require_all_include_patterns
        self._context_window_chars = config.context_window_chars
        self._includes = [CompiledPattern(raw, re.compile(raw, flags)) for raw in config.include_patterns]
        self._excludes = [CompiledPattern(raw, re.compile(raw, flags)) for raw in config.exclude_patterns]

    def match(self, tweet: TweetRecord) -> TweetMatch | None:
        text = normalize_text(tweet.text)
        if not text:
            return None

        if any(pattern.pattern.search(text) for pattern in self._excludes):
            return None

        include_hits = [
            pattern
            for pattern in self._includes
            if pattern.pattern.search(text) is not None
        ]
        if self._require_all:
            matched = len(include_hits) == len(self._includes)
        else:
            matched = bool(include_hits)
        if not matched:
            return None

        if not _relevant_grok_signal(tweet.author_username, text):
            return None

        excerpt = self._excerpt(text, include_hits)
        return TweetMatch(
            tweet=tweet,
            matched_patterns=tuple(pattern.raw for pattern in include_hits),
            excerpt=excerpt,
        )

    def _excerpt(self, text: str, hits: list[CompiledPattern]) -> str:
        first_hit_start = 0
        for pattern in hits:
            match = pattern.pattern.search(text)
            if match:
                first_hit_start = match.start()
                break
        half_window = max(30, self._context_window_chars // 2)
        start = max(0, first_hit_start - half_window)
        end = min(len(text), first_hit_start + half_window)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_GROK_PRODUCT = re.compile(r"\b(?:grok|supergrok|xai|x\.ai)\b", re.IGNORECASE)
_GROK_QUOTA = re.compile(
    r"\b(?:usage|quota|limits?|allowance|weekly|credits?|tokens?|banked)\b",
    re.IGNORECASE,
)


def _relevant_grok_signal(author: str, text: str) -> bool:
    group = account_group_for_handle(author)
    if group is None or not group.startswith("xai-"):
        return True
    if _GROK_QUOTA.search(text) is None:
        return False
    # Broad company and personal accounts discuss many unrelated resets.
    if group in {"xai-official", "xai-people"}:
        return _GROK_PRODUCT.search(text) is not None
    return True
