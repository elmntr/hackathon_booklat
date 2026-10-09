"""Incremental passage alignment with teacher-reviewable marks."""
from dataclasses import dataclass, replace
from typing import Literal

from rapidfuzz.fuzz import ratio

Status = Literal["not_reached", "correct", "substitution", "omission"]


@dataclass
class HeardWord:
    text: str
    t0: float
    t1: float


@dataclass
class Mark:
    idx: int
    status: Status = "not_reached"
    repeats: int = 0
    heard: str | None = None
    t0: float | None = None
    t1: float | None = None
    self_corrected: bool = False


def normalize(s: str) -> str:
    """Remove punctuation while preserving Unicode letters and digits."""
    return "".join(c for c in s.lower() if c.isalnum())


def matches(a: str, b: str, cfg: dict) -> bool:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return False
    if min(len(a), len(b)) <= cfg["exact_match_max_len"]:
        return a == b
    return ratio(a, b) >= cfg["similarity_threshold"]


class Aligner:
    def __init__(self, passage_text: str, cfg: dict):
        self.tokens = passage_text.split()
        self.norm = [normalize(t) for t in self.tokens]
        self.marks = [Mark(i) for i in range(len(self.tokens))]
        self.cfg = cfg["aligner"]
        self.ignore = {normalize(w) for w in cfg["asr"]["ignore_words"]}
        self.p = 0
        self.first_t: float | None = None
        self.last_t: float | None = None

    def _mark(self, idx: int, status: Status, word: HeardWord) -> None:
        mark = self.marks[idx]
        mark.status = status
        mark.heard, mark.t0, mark.t1 = word.text, word.t0, word.t1

    def feed(self, words: list[HeardWord]) -> set[int]:
        """Consume ordered recognizer words, returning changed indices."""
        changed: set[int] = set()
        n = len(self.tokens)
        for word in words:
            h = normalize(word.text)
            if not h or h in self.ignore:
                continue
            if self.first_t is None:
                self.first_t = word.t0
            self.last_t = max(self.last_t or word.t1, word.t1)
            if self.p < n and matches(h, self.norm[self.p], self.cfg):
                self._mark(self.p, "correct", word)
                changed.add(self.p)
                self.p += 1
                continue
            previous = next((self.p - k for k in range(1, self.cfg["lookback"] + 1)
                             if self.p - k >= 0 and matches(h, self.norm[self.p-k], self.cfg)), None)
            if previous is not None:
                mark = self.marks[previous]
                if mark.status == "substitution":
                    self._mark(previous, "correct", word)
                    mark.self_corrected = True
                else:
                    mark.repeats += 1
                changed.add(previous)
                continue
            ahead = next((self.p + k for k in range(1, self.cfg["lookahead"] + 1)
                          if self.p + k < n and matches(h, self.norm[self.p+k], self.cfg)), None)
            if ahead is not None:
                for idx in range(self.p, ahead):
                    self.marks[idx].status = "omission"
                    changed.add(idx)
                self._mark(ahead, "correct", word)
                changed.add(ahead)
                self.p = ahead + 1
            elif self.p < n:
                self._mark(self.p, "substitution", word)
                changed.add(self.p)
                self.p += 1
        return changed

    def snapshot(self) -> list[Mark]:
        return [replace(mark) for mark in self.marks]
