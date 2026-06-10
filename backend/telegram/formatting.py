_SPLIT_LIMIT = 300


def split_message(text: str, limit: int = _SPLIT_LIMIT) -> list[str]:
    """
    Return [text] if within limit, or [first, second] split at the last natural
    break before the limit: paragraph (\\n\\n) > sentence ('. ') > line (\\n).
    Falls back to a hard split at the limit if no natural break is found.

    Limitation: only one split is performed, so if the second part exceeds the
    limit the caller receives it unsplit. Replies are expected to stay within
    2× the limit; THE LLM PROMPT SHOULD ENFORCE THIS.
    """
    if len(text) <= limit:
        return [text]

    window = text[:limit]

    for sep in ("\n\n", ". ", "\n"):
        idx = window.rfind(sep)
        if idx > 0:
            cut = idx + len(sep)
            return [text[:cut].rstrip(), text[cut:].lstrip()]

    return [text[:limit], text[limit:]]
