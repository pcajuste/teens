"""Unit tests for the structured_qa PII scrubber (issue #52). Flag-only
by contract -- these tests check pattern detection, not any auto-clear
behavior, since scrub() never approves/rejects anything itself."""
from __future__ import annotations

from app.services import text_moderation_service


def test_scrub_detects_email():
    result = text_moderation_service.scrub("reach me at teen@example.com anytime")
    assert any(f.pattern == "email" for f in result.flags)
    assert "[redacted]" in result.masked_text
    assert "teen@example.com" not in result.masked_text


def test_scrub_detects_phone_variants():
    for phone in ["512-555-0100", "(512) 555-0100", "512.555.0100", "+1 512 555 0100"]:
        result = text_moderation_service.scrub(f"call me at {phone}")
        assert any(f.pattern == "phone" for f in result.flags), phone


def test_scrub_detects_address_like_pattern():
    result = text_moderation_service.scrub("I live at 123 Main Street near the school")
    assert any(f.pattern == "address" for f in result.flags)


def test_scrub_detects_banned_terms():
    result = text_moderation_service.scrub("I go to Austin High School and love it")
    assert any(f.pattern.startswith("banned_term:") for f in result.flags)


def test_scrub_clean_text_has_no_flags():
    result = text_moderation_service.scrub("The packaging felt premium and the colors were great.")
    assert result.flags == []
    assert result.masked_text == "The packaging felt premium and the colors were great."


def test_scrub_resilient_on_edge_inputs():
    for text in ["", "🎉" * 50, "a" * 10_000]:
        result = text_moderation_service.scrub(text)
        assert isinstance(result.flags, list)


def test_scrub_answers_aggregates_with_question_id_context():
    qa_answers = [
        {"question_id": "q1", "answer_text": "Contact me at teen@example.com"},
        {"question_id": "q2", "answer_text": "No PII here"},
    ]
    flags = text_moderation_service.scrub_answers(qa_answers)
    assert any(f["question_id"] == "q1" and f["pattern"] == "email" for f in flags)
    assert all(f["question_id"] != "q2" for f in flags)
