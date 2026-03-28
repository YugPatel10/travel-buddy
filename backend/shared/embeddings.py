"""Titan Embed v2 and Pinecone helper utilities."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
from pinecone import Pinecone

logger = logging.getLogger(__name__)

# Bedrock model ID for Amazon Titan Embed v2
TITAN_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
TITAN_EMBED_DIMENSION = 1024


def _get_bedrock_client():
    """Return a Bedrock Runtime client."""
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def _get_pinecone_index():
    """Return a Pinecone Index instance."""
    api_key = os.environ.get("PINECONE_API_KEY", "")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "travel-buddy")
    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


def generate_embedding(text: str) -> list[float]:
    """Generate a text embedding using Amazon Titan Embed v2 via Bedrock.

    Args:
        text: The input text to embed (max ~8,000 tokens).

    Returns:
        A list of 1024 floats representing the embedding vector.
    """
    client = _get_bedrock_client()
    body = json.dumps({
        "inputText": text,
        "dimensions": TITAN_EMBED_DIMENSION,
        "normalize": True,
    })
    response = client.invoke_model(
        modelId=TITAN_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def upsert_vectors(vectors: list[dict[str, Any]]) -> None:
    """Upsert vectors into the Pinecone index.

    Args:
        vectors: List of dicts with keys: id, values, metadata.
            Example: [{"id": "doc-123-chunk-0", "values": [...], "metadata": {...}}]
    """
    index = _get_pinecone_index()
    # Pinecone supports batches of up to 100 vectors
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)
    logger.info("Upserted %d vectors to Pinecone", len(vectors))


def query_vectors(
    embedding: list[float], top_k: int = 5, filters: dict | None = None
) -> list[dict]:
    """Query the Pinecone index for similar vectors.

    Args:
        embedding: The query embedding vector.
        top_k: Number of results to return.
        filters: Optional metadata filters (e.g. {"userId": "u1"}).

    Returns:
        List of match dicts with id, score, and metadata.
    """
    index = _get_pinecone_index()
    kwargs: dict[str, Any] = {
        "vector": embedding,
        "top_k": top_k,
        "include_metadata": True,
    }
    if filters:
        kwargs["filter"] = filters
    response = index.query(**kwargs)
    return [
        {"id": m.id, "score": m.score, "metadata": m.metadata}
        for m in response.matches
    ]
