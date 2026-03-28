"""Chat Lambda — accepts user messages and returns placeholder AI responses.

Routes handled (via API Gateway proxy integration):
  POST   /chat                → send_message
  GET    /chat/{tripId}       → get_history
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any

import ulid

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
# Route handlers
# ---------------------------------------------------------------------------

def send_message(event: dict) -> dict:
    """Accept a user message and return a placeholder AI response.

    Expects JSON body:
      {
        "message": "What's the weather like in Tokyo?",
        "tripId": "<optional>"
      }
    """
    user_id = _user_id(event)
    data = _body(event)

    message = data.get("message", "").strip()
    if not message:
        return _response(400, {"error": "Missing required field: message"})

    trip_id = data.get("tripId")
    now = datetime.utcnow().isoformat()
    message_id = str(ulid.new())

    # Placeholder response — will be replaced by LangGraph agent integration
    return _response(200, {
        "messageId": message_id,
        "tripId": trip_id,
        "userMessage": message,
        "reply": (
            "Thanks for your message! The AI travel assistant is not yet connected. "
            "This is a placeholder response. Once the LangGraph agent is wired up, "
            "I'll be able to help with flight searches, hotel recommendations, "
            "gym finders, and more."
        ),
        "timestamp": now,
    })


def get_history(event: dict) -> dict:
    """Return placeholder chat history for a trip.

    Will be backed by DynamoDB once the agent is integrated.
    """
    _user_id(event)  # auth check
    trip_id = event["pathParameters"]["tripId"]

    return _response(200, {
        "tripId": trip_id,
        "messages": [],
        "note": "Chat history will be available once the AI agent is integrated.",
    })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, str], Any] = {
    ("POST", "/chat"):              send_message,
    ("GET",  "/chat/{tripId}"):     get_history,
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
