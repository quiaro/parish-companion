from telegram.formatting import split_message

_WORD = "a" * 20  # 20-char filler word


def _words(n: int) -> str:
    return (" ".join([_WORD] * n)).strip()


def test_short_text_returned_as_single_part() -> None:
    """AC1: text within limit is not split."""
    text = _words(5)  # well under 300 chars
    assert split_message(text) == [text]


def test_long_text_split_at_paragraph_break() -> None:
    """AC1: text over limit with \\n\\n is split at the paragraph boundary."""
    first = _words(8)                   # ~167 chars — fits in the 300-char window
    second = _words(8)
    text = f"{first}\n\n{second}"
    parts = split_message(text)
    assert len(parts) == 2
    assert parts[0] == first
    assert parts[1] == second


def test_long_text_split_at_sentence_boundary() -> None:
    """AC1: text over limit with no paragraph break is split at the last '. '."""
    first = _words(8) + "."             # sentence ending with a period (~168 chars)
    second = _words(8)
    text = f"{first} {second}"          # total ~336 chars — over limit; '. ' within window
    parts = split_message(text)
    assert len(parts) == 2
    assert parts[0] == first
    assert parts[1] == second


def test_long_text_hard_split_when_no_natural_break() -> None:
    """AC1: text over limit with no natural break is hard-split at the limit."""
    text = "a" * 400
    parts = split_message(text, limit=300)
    assert len(parts) == 2
    assert parts[0] == "a" * 300
    assert parts[1] == "a" * 100
