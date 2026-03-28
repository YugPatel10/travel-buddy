"""Document Lambda — presigned URL generation and document management.

Routes handled (via API Gateway proxy integration):
  POST   /documents/upload-url   → generate_upload_url
  GET    /documents              → list_documents
  GET    /documents/{docId}      → get_document
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
import ulid

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.config import DOCUMENTS_TABLE, UPLOAD_BUCKET
from shared.dynamo import put_item, get_item, query_items


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3_client():
    """Lazy-initialise the S3 client (reused across warm invocations)."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _user_id(event: dict) -> str:
    """Extract the Cognito user ID (sub) from the authorizer claims."""
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    sub = claims.get("sub")
    if not sub:
        raise PermissionError("Missing authentication claims")
    return sub


def _body(event: dict) -> dict:
    """Parse the JSON request body."""
    raw = event.get("body") or "{}"
    return json.loads(raw) if isinstance(raw, str) else raw


def _response(status: int, body: Any) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=_json_serial),
    }


def _json_serial(obj: Any) -> Any:
    """Handle Decimal and datetime serialisation for json.dumps."""
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# ---------------------------------------------------------------------------
# Allowed upload content types
# ---------------------------------------------------------------------------

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}

_PRESIGNED_URL_EXPIRY = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def generate_upload_url(event: dict) -> dict:
    """Generate a presigned S3 PUT URL and create a document record.

    Expects JSON body:
      {
        "fileName": "booking.pdf",
        "contentType": "application/pdf",
        "tripId": "<optional>"
      }
    """
    user_id = _user_id(event)
    data = _body(event)

    file_name = data.get("fileName")
    content_type = data.get("contentType", "application/pdf")

    if not file_name:
        return _response(400, {"error": "Missing required field: fileName"})

    if content_type not in _ALLOWED_CONTENT_TYPES:
        return _response(
            400,
            {"error": f"Unsupported content type: {content_type}. Allowed: {sorted(_ALLOWED_CONTENT_TYPES)}"},
        )

    doc_id = str(ulid.new())
    s3_key = f"uploads/{user_id}/{doc_id}/{file_name}"
    now = datetime.utcnow().isoformat()

    # Create the document record in DynamoDB
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"DOC#{doc_id}",
        "docId": doc_id,
        "userId": user_id,
        "tripId": data.get("tripId"),
        "s3Key": s3_key,
        "fileName": file_name,
        "status": "uploaded",
        "parsedData": None,
        "createdAt": now,
    }
    put_item(DOCUMENTS_TABLE, item)

    # Generate presigned PUT URL
    s3 = _get_s3_client()
    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": UPLOAD_BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=_PRESIGNED_URL_EXPIRY,
    )

    return _response(201, {
        "uploadUrl": presigned_url,
        "docId": doc_id,
        "s3Key": s3_key,
        "expiresIn": _PRESIGNED_URL_EXPIRY,
    })


def list_documents(event: dict) -> dict:
    """List all documents belonging to the authenticated user."""
    user_id = _user_id(event)
    items = query_items(DOCUMENTS_TABLE, "PK", f"USER#{user_id}", sk_prefix="DOC#")
    return _response(200, [_strip_keys(i) for i in items])


def get_document(event: dict) -> dict:
    """Get a single document by ID, including parsed data."""
    user_id = _user_id(event)
    doc_id = event["pathParameters"]["docId"]
    item = get_item(DOCUMENTS_TABLE, {"PK": f"USER#{user_id}", "SK": f"DOC#{doc_id}"})
    if not item:
        return _response(404, {"error": "Document not found"})
    return _response(200, _strip_keys(item))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _strip_keys(item: dict) -> dict:
    """Remove DynamoDB composite keys (PK/SK) from the response payload."""
    return {k: v for k, v in item.items() if k not in ("PK", "SK")}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, str], Any] = {
    ("POST", "/documents/upload-url"):  generate_upload_url,
    ("GET",  "/documents"):             list_documents,
    ("GET",  "/documents/{docId}"):     get_document,
}


def handler(event: dict, context: object) -> dict:
    """AWS Lambda entry point — routes to the correct handler."""
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")

    route_fn = _ROUTES.get((method, resource))
    if not route_fn:
        return _response(404, {"error": f"Route not found: {method} {resource}"})

    try:
        return route_fn(event)
    except PermissionError as exc:
        return _response(401, {"error": str(exc)})
    except Exception:
        traceback.print_exc()
        return _response(500, {"error": "Internal server error"})
