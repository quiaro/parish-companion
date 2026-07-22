"""
Offline ingestion pipeline for the Bible verse bank (K-07 prerequisite).

Reads the curated, pre-tagged verse CSV, synthesizes an embedding text blob per verse
from its tags and example phrasings (not the raw verse text), embeds it, and upserts each
verse into Qdrant. Run manually after any change to the verse CSV:

    docker compose exec backend python scripts/ingest_verses.py [path/to/verses.csv]

Idempotent: point IDs are derived deterministically from each verse's `reference`, so
re-running the script updates existing points rather than duplicating them.
"""

import asyncio
import csv
import json
import logging
import sys
import uuid
from dataclasses import dataclass

from openai import AsyncOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from commands.comfort.models import EmotionalTag, SituationalTag
from config import settings

logger = logging.getLogger(__name__)

_DEFAULT_CSV_PATH = "data/bible_OEB_verses.csv"

# Fixed, arbitrary namespace for deriving deterministic point IDs from verse references —
# any fixed UUID works, it just needs to stay the same across runs for idempotency.
_POINT_ID_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


@dataclass
class VerseRow:
    reference: str
    verse_text: str
    emotional_tags: list[str]
    situational_tags: list[str]
    example_user_phrasings: list[str]


def _point_id(reference: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, reference))


def _synthesize_embedding_text(row: VerseRow) -> str:
    """Embeds a synthesized description of the verse's tags and example phrasings —
    not the raw verse text — so a parishioner's free-text message resembles this
    description semantically, rather than needing to resemble Scripture's own wording."""
    parts = []
    if row.emotional_tags:
        parts.append("Emotional tags: " + ", ".join(row.emotional_tags) + ".")
    if row.situational_tags:
        parts.append("Situational tags: " + ", ".join(row.situational_tags) + ".")
    if row.example_user_phrasings:
        parts.append("Example phrasings: " + " ".join(row.example_user_phrasings))
    return " ".join(parts)


def load_verses(csv_path: str) -> list[VerseRow]:
    """Parses and validates the verse CSV. Raises on any unrecognized tag rather than
    silently dropping it — this is curated content a human should fix, unlike the
    classifier's runtime output, which is untrusted and handled more leniently."""
    emotional_values = {t.value for t in EmotionalTag}
    situational_values = {t.value for t in SituationalTag}
    rows: list[VerseRow] = []
    problems: list[str] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        for line_num, raw in enumerate(csv.DictReader(f), start=2):
            emotional_tags = json.loads(raw["emotional_tags"])
            situational_tags = json.loads(raw["situational_tags"])
            for tag in emotional_tags:
                if tag not in emotional_values:
                    problems.append(f"line {line_num} ({raw['reference']}): unknown emotional_tag {tag!r}")
            for tag in situational_tags:
                if tag not in situational_values:
                    problems.append(f"line {line_num} ({raw['reference']}): unknown situational_tag {tag!r}")
            rows.append(
                VerseRow(
                    reference=raw["reference"],
                    verse_text=raw["verse"],
                    emotional_tags=emotional_tags,
                    situational_tags=situational_tags,
                    example_user_phrasings=json.loads(raw["example_user_phrasings"]),
                )
            )

    if problems:
        raise ValueError("Invalid tags found in verse CSV:\n" + "\n".join(problems))
    return rows


async def _embed(client: AsyncOpenAI, text: str) -> list[float]:
    response = await client.embeddings.create(
        model=settings.openrouter_embedding_model,
        input=text,
        # Explicit, since the openai SDK otherwise defaults to requesting base64
        # encoding, which this OpenRouter-proxied model doesn't handle correctly.
        encoding_format="float",
    )
    return response.data[0].embedding


def _build_point(row: VerseRow, vector: list[float]) -> PointStruct:
    return PointStruct(
        id=_point_id(row.reference),
        vector=vector,
        payload={
            "reference": row.reference,
            "verse_text": row.verse_text,
            "emotional_tags": row.emotional_tags,
            "situational_tags": row.situational_tags,
        },
    )


async def ingest(csv_path: str = _DEFAULT_CSV_PATH) -> None:
    rows = load_verses(csv_path)
    logger.info("Loaded %d verses from %s", len(rows), csv_path)

    client = AsyncOpenAI(base_url=settings.openrouter_base_url, api_key=settings.openrouter_api_key)
    qdrant = QdrantClient(url=settings.qdrant_url)

    first_vector = await _embed(client, _synthesize_embedding_text(rows[0]))
    if not qdrant.collection_exists(settings.qdrant_collection_name):
        qdrant.create_collection(
            settings.qdrant_collection_name,
            vectors_config=VectorParams(size=len(first_vector), distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d)", settings.qdrant_collection_name, len(first_vector))

    points = [_build_point(rows[0], first_vector)]
    for row in rows[1:]:
        vector = await _embed(client, _synthesize_embedding_text(row))
        points.append(_build_point(row, vector))

    qdrant.upsert(collection_name=settings.qdrant_collection_name, points=points)
    logger.info("Upserted %d verses into Qdrant collection '%s'", len(points), settings.qdrant_collection_name)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_CSV_PATH
    asyncio.run(ingest(path))
