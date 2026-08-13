"""Regex/keyword PII scrubber for structured_qa free-text answers
(issue #52). Runs synchronously at submit time. This is flag-only: its
output feeds the mandatory admin review queue
(insight_feedback_repository.review_response) as reviewer context, but
never itself approves or rejects a response -- every structured_qa
answer requires a human look regardless of flag count, so even a
scrub() bug can only ever under-inform a reviewer, never bypass one."""
from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_ADDRESS_RE = re.compile(
    r"\d{1,6}\s+\w+(\s\w+){0,3}\s(street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard)\b",
    re.IGNORECASE,
)

# v1: a static, conservative list. Product may want a brand/admin-
# configurable or DB-backed list later; not needed for this pass.
BANNED_TERMS: list[str] = [
    "high school",
    "middle school",
    "elementary school",
]


@dataclass(frozen=True, slots=True)
class ScrubFlag:
    pattern: str  # "email" | "phone" | "address" | "banned_term:<term>"
    span: tuple[int, int]
    matched_text: str  # reviewer-only context, never surfaced to the brand


@dataclass(frozen=True, slots=True)
class ScrubResult:
    flags: list[ScrubFlag]
    masked_text: str


def scrub(text: str) -> ScrubResult:
    flags: list[ScrubFlag] = []
    for pattern_name, regex in (("email", _EMAIL_RE), ("phone", _PHONE_RE), ("address", _ADDRESS_RE)):
        for match in regex.finditer(text):
            flags.append(ScrubFlag(pattern=pattern_name, span=match.span(), matched_text=match.group(0)))
    lowered = text.lower()
    for term in BANNED_TERMS:
        start = 0
        while (idx := lowered.find(term, start)) != -1:
            flags.append(ScrubFlag(pattern=f"banned_term:{term}", span=(idx, idx + len(term)), matched_text=text[idx : idx + len(term)]))
            start = idx + len(term)

    masked_text = text
    for flag in sorted(flags, key=lambda f: f.span[0], reverse=True):
        start, end = flag.span
        masked_text = masked_text[:start] + "[redacted]" + masked_text[end:]

    return ScrubResult(flags=sorted(flags, key=lambda f: f.span[0]), masked_text=masked_text)


def scrub_answers(qa_answers: list[dict]) -> list[dict]:
    """Runs scrub() over every answer_text, aggregating flags with
    question_id context for storage in insight_feedback_responses.scrub_flags."""
    aggregated: list[dict] = []
    for answer in qa_answers:
        result = scrub(answer.get("answer_text", ""))
        for flag in result.flags:
            aggregated.append(
                {
                    "question_id": answer.get("question_id"),
                    "pattern": flag.pattern,
                    "span": list(flag.span),
                    "matched_text": flag.matched_text,
                }
            )
    return aggregated
