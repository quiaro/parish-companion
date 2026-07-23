"""
Regression test for the Qdrant result-ordering assumption behind K-07's `j`-pointer
optimization (docs/comfort-technical-summary.md Step F): retrieval only checks one
candidate per position because it assumes results come back sorted by descending
similarity. Runs against an embedded, in-memory Qdrant instance rather than the live
Docker service, so it exercises real qdrant-client ranking behavior, not a mock, while
staying in the normal always-run suite.
"""

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from commands.comfort.retrieval import _require_payload


@pytest.mark.asyncio
async def test_query_points_returns_results_in_non_increasing_similarity_order() -> None:
    client = AsyncQdrantClient(location=":memory:")
    await client.create_collection(
        "ordering_check", vectors_config=VectorParams(size=4, distance=Distance.COSINE)
    )
    await client.upsert(
        "ordering_check",
        points=[
            PointStruct(id=1, vector=[1.0, 0.0, 0.0, 0.0], payload={"reference": "A"}),  # identical to query
            PointStruct(id=2, vector=[0.9, 0.1, 0.0, 0.0], payload={"reference": "B"}),  # close
            PointStruct(id=3, vector=[0.0, 1.0, 0.0, 0.0], payload={"reference": "C"}),  # orthogonal
            PointStruct(id=4, vector=[-1.0, 0.0, 0.0, 0.0], payload={"reference": "D"}),  # opposite
        ],
    )

    response = await client.query_points("ordering_check", query=[1.0, 0.0, 0.0, 0.0], limit=10, with_payload=True)

    references = [_require_payload(p)["reference"] for p in response.points]
    scores = [p.score for p in response.points]

    assert references == ["A", "B", "C", "D"]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
