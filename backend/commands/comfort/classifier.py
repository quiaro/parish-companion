import json
import logging
from enum import Enum
from typing import TypeVar

from langfuse.openai import AsyncOpenAI  # type: ignore[reportPrivateImportUsage]

from commands.comfort.models import ClassificationResult, EmotionalTag, SituationalTag
from config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)

_TagEnum = TypeVar("_TagEnum", bound=Enum)

_EMOTIONAL_TAG_VALUES = [t.value for t in EmotionalTag]
_SITUATIONAL_TAG_VALUES = [t.value for t in SituationalTag]

_SYSTEM_PROMPT = (
    "You are a classifier for a parish pastoral-care bot. A parishioner has submitted a "
    "free-text message describing how they feel or what they're going through. The message "
    "may be in any language (e.g. English or Spanish) — classify it regardless of the "
    "language it's written in, always using the exact English tag values given below, "
    "never translated or transliterated equivalents. Classify it and respond with ONLY a "
    "JSON object with exactly these fields:\n"
    "\n"
    '- "is_crisis": boolean — true if the message describes self-harm, suicidal ideation, '
    "sexual abuse, or physical violence; false otherwise.\n"
    '- "emotional_tags": array of strings — zero or more values from this exact list, and no '
    f"others: {json.dumps(_EMOTIONAL_TAG_VALUES)}\n"
    '- "situational_tags": array of strings — zero or more values from this exact list, and no '
    f"others: {json.dumps(_SITUATIONAL_TAG_VALUES)}\n"
    "\n"
    "Always populate emotional_tags and situational_tags with whichever tags best describe the "
    "message, even when is_crisis is true — this data is used for anonymized aggregate logging "
    "regardless of crisis status. An empty list is valid if nothing in the message matches. Do "
    "not invent tags outside the given lists. Respond with the JSON object only, no other text."
)


def _parse_tags(raw_values: list, tag_enum: type[_TagEnum]) -> list[_TagEnum]:
    tags: list[_TagEnum] = []
    for value in raw_values:
        try:
            tags.append(tag_enum(value))
        except ValueError:
            logger.warning("Unrecognized %s value from classifier: %r", tag_enum.__name__, value)
    return tags


async def classify(text: str) -> ClassificationResult:
    """
    Makes exactly one LLM call returning is_crisis, emotional_tags, and situational_tags
    together. Raises on API failure or a response that can't be parsed at all;
    tags with unrecognized values are dropped individually rather than failing the whole call.
    """
    completion = await client.chat.completions.create(
        model=settings.openrouter_chat_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        timeout=30.0,
        name="comfort.classify",  # type: ignore[call-overload]  # Langfuse-injected kwarg, stripped before the real API call
    )
    content = completion.choices[0].message.content
    if content is None:
        raise ValueError("Classifier returned no content")

    raw = json.loads(content)
    return ClassificationResult(
        is_crisis=bool(raw["is_crisis"]),
        emotional_tags=_parse_tags(raw.get("emotional_tags", []), EmotionalTag),
        situational_tags=_parse_tags(raw.get("situational_tags", []), SituationalTag),
    )
