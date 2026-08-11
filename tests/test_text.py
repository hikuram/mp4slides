import pytest

from mp4slides.text import normalize_transcript_text


def test_preserve_newlines() -> None:
    assert normalize_transcript_text("a\nb\n\nc", "preserve") == "a\nb\n\nc"


def test_replace_newlines_with_spaces() -> None:
    text = "first line\nsecond line\r\nthird line"
    assert normalize_transcript_text(text, "space") == "first line second line third line"


def test_preserve_paragraph_breaks() -> None:
    text = "first\nsecond\n\nthird\nfourth"
    assert normalize_transcript_text(text, "paragraph") == "first second\n\nthird fourth"


def test_invalid_newline_mode() -> None:
    with pytest.raises(ValueError):
        normalize_transcript_text("text", "invalid")
