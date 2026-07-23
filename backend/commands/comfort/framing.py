"""K-08: writes a brief pastoral reflection to accompany the verse 
already selected by K-07's retrieve_passage."""

from openai import AsyncOpenAI

from commands.comfort.retrieval import RetrievedPassage
from config import settings

client = AsyncOpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)

_LANGUAGE_NAMES = {"en": "English", "es": "Spanish"}

_SYSTEM_PROMPT = (
    "You are writing a short pastoral reflection to accompany a Bible verse for a parishioner "
    "of a Catholic parish. You will be given the parishioner's message and the Bible verse "
    "already selected for them — do not classify, tag, or re-evaluate their message in any "
    "way. Write a reflection of no more than 3 sentences that helps the parishioner connect "
    "the verse to their situation. Be warm and pastoral: do not be prescriptive, clinical, or "
    "preachy, and do not repeat the verse text itself. Respond with the reflection only, no "
    "other text."
)


async def frame_passage(raw_text: str, passage: RetrievedPassage, language: str = "en") -> str:
    """
    One LLM call, no re-classification: receives the parishioner's message and the verse
    already chosen by retrieval, and returns a short reflection. Never called on the Step
    G fallback path (see flow.py) — there's no real match to frame there.
    """
    language_name = _LANGUAGE_NAMES.get(language, language)
    user_message = (
        f"Parishioner's message: {raw_text}\n\n"
        f"Selected verse ({passage.reference}): {passage.verse_text}\n\n"
        f"Write the reflection in {language_name}."
    )
    completion = await client.chat.completions.create(
        model=settings.openrouter_chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        timeout=30.0,
    )
    content = completion.choices[0].message.content
    if content is None:
        raise ValueError("Framing call returned no content")
    return content.strip()
