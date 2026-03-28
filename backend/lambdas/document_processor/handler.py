"""Document Processor Lambda — triggered by S3 object creation events.

Receives S3 event notifications for objects uploaded to the `uploads/` prefix
and processes them through the document ingestion pipeline:
  1. Extract text via Amazon Textract
  2. Structure extracted data using Bedrock Claude
  3. Generate embeddings via Amazon Titan Embed v2
  4. Store embeddings in Pinecone
  5. Update document status in DynamoDB
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DOCUMENTS_TABLE = os.environ.get("DOCUMENTS_TABLE", "")
DOCUMENTS_BUCKET = os.environ.get("DOCUMENTS_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Bedrock model for intelligent parsing
CLAUDE_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


# ---------------------------------------------------------------------------
# S3 key parsing
# ---------------------------------------------------------------------------

def _parse_s3_key(key: str) -> dict:
    """Parse the S3 key to extract userId, docId, and filename.

    Expected format: uploads/{userId}/{docId}/{filename}
    """
    parts = key.split("/")
    if len(parts) < 4:
        raise ValueError(f"Unexpected S3 key format: {key}")
    return {
        "userId": parts[1],
        "docId": parts[2],
        "fileName": "/".join(parts[3:]),
    }


# ---------------------------------------------------------------------------
# DynamoDB status helpers
# ---------------------------------------------------------------------------

def _update_document_status(
    user_id: str,
    doc_id: str,
    status: str,
    parsed_data: dict | None = None,
) -> None:
    """Update the document status in the Documents DynamoDB table."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from dynamo import update_item

    updates: dict = {
        "status": status,
        "updatedAt": datetime.utcnow().isoformat(),
    }
    if parsed_data is not None:
        updates["parsedData"] = parsed_data

    update_item(
        DOCUMENTS_TABLE,
        {"PK": f"USER#{user_id}", "SK": f"DOC#{doc_id}"},
        updates,
    )
    logger.info("Updated doc %s status to '%s'", doc_id, status)


# ---------------------------------------------------------------------------
# Step 1: Textract text extraction
# ---------------------------------------------------------------------------

def _extract_text_with_textract(bucket: str, key: str) -> str:
    """Call Amazon Textract analyze_document to extract text from a document.

    Uses the S3 object directly. Returns the concatenated extracted text.
    """
    textract = boto3.client("textract", region_name=AWS_REGION)

    response = textract.analyze_document(
        Document={"S3Object": {"Bucket": bucket, "Name": key}},
        FeatureTypes=["TABLES", "FORMS"],
    )

    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block.get("Text", ""))

    extracted = "\n".join(lines)
    logger.info(
        "Textract extracted %d lines (%d chars) from %s",
        len(lines),
        len(extracted),
        key,
    )
    return extracted


# ---------------------------------------------------------------------------
# Step 2: Structure extracted text with Bedrock Claude
# ---------------------------------------------------------------------------

def _structure_text_with_bedrock(raw_text: str) -> dict:
    """Use Bedrock Claude to parse raw text into structured JSON.

    Extracts: dates, locations, costs, confirmation numbers, and content type.
    """
    bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    prompt = (
        "You are a travel document parser. Analyze the following text extracted "
        "from a travel document and return a JSON object with these fields:\n"
        "- dates: list of date strings found (ISO 8601 format when possible)\n"
        "- locations: list of location/city/country names found\n"
        "- costs: list of objects with {amount, currency, description}\n"
        "- confirmationNumbers: list of booking/confirmation numbers found\n"
        "- contentType: one of 'itinerary', 'booking', 'contract', or 'general'\n"
        "- summary: a brief 1-2 sentence summary of the document\n\n"
        "Return ONLY valid JSON, no markdown fences or extra text.\n\n"
        f"Document text:\n{raw_text[:8000]}"
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    })

    response = bedrock.invoke_model(
        modelId=CLAUDE_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(response["body"].read())
    content_text = result["content"][0]["text"]

    try:
        structured = json.loads(content_text)
    except json.JSONDecodeError:
        logger.warning("Claude returned non-JSON, wrapping as general content")
        structured = {
            "dates": [],
            "locations": [],
            "costs": [],
            "confirmationNumbers": [],
            "contentType": "general",
            "summary": content_text[:200],
        }

    logger.info("Structured data: contentType=%s", structured.get("contentType"))
    return structured


# ---------------------------------------------------------------------------
# Step 3 & 4: Embedding generation + Pinecone upsert
# ---------------------------------------------------------------------------

def _embed_and_store(
    raw_text: str,
    structured_data: dict,
    user_id: str,
    doc_id: str,
    trip_id: str | None = None,
) -> None:
    """Generate embeddings for the document text and upsert to Pinecone.

    Chunks the text into segments, generates an embedding for each,
    and stores them with metadata for filtering.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from embeddings import generate_embedding, upsert_vectors

    # Chunk text into ~1000 char segments for better retrieval
    chunks = _chunk_text(raw_text, max_chars=1000)
    if not chunks:
        logger.warning("No text chunks to embed for doc %s", doc_id)
        return

    content_type = structured_data.get("contentType", "general")
    locations = structured_data.get("locations", [])
    dates = structured_data.get("dates", [])

    vectors = []
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        vector_id = f"{doc_id}-chunk-{i}"
        metadata = {
            "userId": user_id,
            "docId": doc_id,
            "contentType": content_type,
            "chunkIndex": i,
            "text": chunk[:500],  # Store truncated text for retrieval context
        }
        if trip_id:
            metadata["tripId"] = trip_id
        if locations:
            metadata["location"] = locations[0]
        if dates:
            metadata["extractedDate"] = dates[0]

        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": metadata,
        })

    upsert_vectors(vectors)
    logger.info("Embedded and stored %d chunks for doc %s", len(vectors), doc_id)


def _chunk_text(text: str, max_chars: int = 1000) -> list[str]:
    """Split text into chunks of approximately max_chars, breaking at newlines."""
    if not text.strip():
        return []

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = line
        else:
            current = current + "\n" + line if current else line
    if current.strip():
        chunks.append(current.strip())
    return chunks


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def _process_document(bucket: str, key: str) -> None:
    """Run the full document ingestion pipeline for a single S3 object."""
    # Parse S3 key for userId and docId
    key_info = _parse_s3_key(key)
    user_id = key_info["userId"]
    doc_id = key_info["docId"]

    # Step 0: Update status to 'processing'
    _update_document_status(user_id, doc_id, "processing")

    try:
        # Step 1: Extract text with Textract
        raw_text = _extract_text_with_textract(bucket, key)
        if not raw_text.strip():
            logger.warning("No text extracted from %s", key)
            _update_document_status(user_id, doc_id, "failed")
            return

        # Step 2: Structure text with Bedrock Claude
        structured_data = _structure_text_with_bedrock(raw_text)

        # Step 3 & 4: Generate embeddings and store in Pinecone
        # Try to find tripId from the document record
        trip_id = _get_trip_id_for_doc(user_id, doc_id)
        _embed_and_store(raw_text, structured_data, user_id, doc_id, trip_id)

        # Step 5: Update status to 'parsed' with structured data
        _update_document_status(user_id, doc_id, "parsed", parsed_data=structured_data)

    except Exception:
        logger.exception("Failed to process document %s/%s", bucket, key)
        _update_document_status(user_id, doc_id, "failed")
        raise


def _get_trip_id_for_doc(user_id: str, doc_id: str) -> str | None:
    """Look up the tripId associated with a document, if any."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from dynamo import get_item

    item = get_item(DOCUMENTS_TABLE, {"PK": f"USER#{user_id}", "SK": f"DOC#{doc_id}"})
    if item:
        return item.get("tripId")
    return None


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point — processes S3 event notifications."""
    logger.info("Received event: %s", json.dumps(event))

    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        size = record["s3"]["object"].get("size", 0)

        logger.info(
            "Processing object: bucket=%s, key=%s, size=%d",
            bucket,
            key,
            size,
        )

        _process_document(bucket, key)

    return {"statusCode": 200, "body": "Processing complete"}
