"""
K-07: retrieves a Bible verse for a parishioner's free-text message via semantic search 
against the Qdrant verse bank populated by scripts/ingest_verses.py.
"""

import asyncio
import logging
import random
from dataclasses import dataclass

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from commands.comfort.constants import FALLBACK_EMOTIONAL_TAGS
from commands.comfort.models import ClassificationResult
from config import settings
from db.parishioners import get_recent_sent_passages

logger = logging.getLogger(__name__)

_MAX_K = 40

client = AsyncOpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)
qdrant = AsyncQdrantClient(url=settings.qdrant_url)


@dataclass
class RetrievedPassage:
    reference: str
    verse_text: str
    verse_text_es: str
    is_fallback: bool  # Step G: no framing


_TRANSLATION_SYSTEM_PROMPT = (
    "Translate the following message to English. Preserve the emotional tone and meaning "
    "as closely as possible. Respond with the translation only, no other text."
)


async def _translate_to_english(text: str) -> str:
    """
    Retrieval's synthesized verse descriptions (see scripts/ingest_verses.py) are embedded
    in English, so a non-English query is translated before embedding to keep retrieval in
    a single embedding space rather than maintaining a parallel per-language index or
    relying on a multilingual embedding model's cross-lingual alignment. Classification
    works directly on the original text so (Step B) is unaffected by this.
    """
    completion = await client.chat.completions.create(
        model=settings.openrouter_chat_model,
        messages=[
            {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        timeout=30.0,
    )
    content = completion.choices[0].message.content
    if content is None:
        raise ValueError("Translation call returned no content")
    return content.strip()


async def _embed(text: str) -> list[float]:
    response = await client.embeddings.create(
        model=settings.openrouter_embedding_model,
        input=text,
        # Explicit, since the openai SDK otherwise defaults to requesting base64
        # encoding, which this OpenRouter-proxied model doesn't handle correctly.
        encoding_format="float",
    )
    return response.data[0].embedding


def _require_payload(point) -> dict:
    if point.payload is None:
        raise RuntimeError(f"Qdrant point {point.id!r} has no payload — verse bank data is corrupt")
    return point.payload


def _log_if_tag_mismatch(reference: str, payload: dict, classification: ClassificationResult) -> None:
    """Step F.5: a feedback signal for vocabulary/curation gaps, not an error."""
    classified_tags = {t.value for t in classification.emotional_tags} | {
        t.value for t in classification.situational_tags
    }
    verse_tags = set(payload.get("emotional_tags", [])) | set(payload.get("situational_tags", []))
    if classified_tags and verse_tags and classified_tags.isdisjoint(verse_tags):
        logger.warning(
            "Retrieved passage %s shares no tags with classified input (classified=%s, verse=%s)",
            reference,
            sorted(classified_tags),
            sorted(verse_tags),
        )


async def _random_fallback_passage() -> RetrievedPassage:
    """
    Step G: no relevant match was found. Rather than force a bad match or re-send a
    previously-sent passage — which could be irrelevant to what the parishioner just shared —
    a random encouraging verse is presented instead. Deliberately not filtered against the
    parishioner's sent history. Allowing a repeat here (though, unlikely) is an acceptable 
    simplification, unlike the real-match path above.
    """
    tag_values = [t.value for t in FALLBACK_EMOTIONAL_TAGS]
    points, _ = await qdrant.scroll(
        collection_name=settings.qdrant_collection_name,
        scroll_filter=Filter(must=[FieldCondition(key="emotional_tags", match=MatchAny(any=tag_values))]),
        limit=1000,
        with_payload=True,
    )
    if not points:
        raise RuntimeError(
            f"No verses tagged with any of {tag_values} found in Qdrant collection "
            f"{settings.qdrant_collection_name!r} — the fallback pool must never be empty."
        )
    chosen = random.choice(points)
    payload = _require_payload(chosen)
    return RetrievedPassage(
        reference=payload["reference"],
        verse_text=payload["verse_text"],
        verse_text_es=payload["verse_text_es"],
        is_fallback=True,
    )


async def retrieve_passage(
    telegram_user_id: int, text: str, classification: ClassificationResult, language: str = "en"
) -> RetrievedPassage:
    """
    Step F: embeds the parishioner's raw text (translated to English first if `language`
    isn't English), then walks Qdrant's similarity-sorted top-`_MAX_K` results with a 
    `j`-pointer. A below-threshold hit means nothing later in the batch could score 
    higher either, so it goes straight to the Step G fallback. A recently-sent hit 
    just advances `j`.
    """
    recent_sent = await asyncio.to_thread(get_recent_sent_passages, telegram_user_id)
    recently_sent_references = {p.passage_reference for p in recent_sent}

    text_to_embed = await _translate_to_english(text) if language != "en" else text
    vector = await _embed(text_to_embed)
    response = await qdrant.query_points(
        collection_name=settings.qdrant_collection_name, query=vector, limit=_MAX_K, with_payload=True
    )
    for candidate in response.points:
        if candidate.score < settings.comfort_similarity_threshold:
            return await _random_fallback_passage()
        payload = _require_payload(candidate)
        reference = payload["reference"]
        if reference not in recently_sent_references:
            _log_if_tag_mismatch(reference, payload, classification)
            return RetrievedPassage(
                reference=reference,
                verse_text=payload["verse_text"],
                verse_text_es=payload["verse_text_es"],
                is_fallback=False,
            )

    return await _random_fallback_passage()
