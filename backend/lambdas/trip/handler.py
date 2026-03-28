"""Trip Lambda — CRUD operations for trips in DynamoDB.

Routes handled (via API Gateway proxy integration):
  POST   /trips              → create_trip
  GET    /trips              → list_trips
  GET    /trips/{tripId}     → get_trip
  PUT    /trips/{tripId}     → update_trip
  DELETE /trips/{tripId}     → delete_trip
  GET    /trips/{tripId}/scouts        → get_scouts
  GET    /trips/{tripId}/scouts/trends → get_scout_trends
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Any

import ulid

import sys, os
# Allow imports from the shared package that lives alongside the lambdas dir.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.config import TRIPS_TABLE, SCOUT_RESULTS_TABLE
from shared.dynamo import put_item, get_item, query_items, delete_item, update_item


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

def create_trip(event: dict) -> dict:
    user_id = _user_id(event)
    data = _body(event)

    required = ("destination", "startDate", "endDate")
    missing = [f for f in required if f not in data]
    if missing:
        return _response(400, {"error": f"Missing required fields: {', '.join(missing)}"})

    trip_id = str(ulid.new())
    now = datetime.utcnow().isoformat()

    preferences = data.get("preferences", {})
    price_alerts = data.get("priceAlerts", {})

    item = {
        "PK": f"USER#{user_id}",
        "SK": f"TRIP#{trip_id}",
        "tripId": trip_id,
        "userId": user_id,
        "destination": data["destination"],
        "startDate": data["startDate"],
        "endDate": data["endDate"],
        "status": data.get("status", "planning"),
        "preferences": {
            "budget": preferences.get("budget"),
            "interests": preferences.get("interests", []),
            "fitnessNeeds": preferences.get("fitnessNeeds", []),
            "equipmentPrefs": preferences.get("equipmentPrefs", []),
        },
        "priceAlerts": {
            "maxFlight": price_alerts.get("maxFlight"),
            "maxHotelPerNight": price_alerts.get("maxHotelPerNight"),
        },
        "createdAt": now,
        "updatedAt": now,
    }

    if "destinationCoords" in data:
        item["destinationCoords"] = data["destinationCoords"]

    put_item(TRIPS_TABLE, item)
    return _response(201, _strip_keys(item))


def list_trips(event: dict) -> dict:
    user_id = _user_id(event)
    items = query_items(TRIPS_TABLE, "PK", f"USER#{user_id}", sk_prefix="TRIP#")
    return _response(200, [_strip_keys(i) for i in items])


def get_trip(event: dict) -> dict:
    user_id = _user_id(event)
    trip_id = event["pathParameters"]["tripId"]
    item = get_item(TRIPS_TABLE, {"PK": f"USER#{user_id}", "SK": f"TRIP#{trip_id}"})
    if not item:
        return _response(404, {"error": "Trip not found"})
    return _response(200, _strip_keys(item))


def update_trip(event: dict) -> dict:
    user_id = _user_id(event)
    trip_id = event["pathParameters"]["tripId"]
    key = {"PK": f"USER#{user_id}", "SK": f"TRIP#{trip_id}"}

    existing = get_item(TRIPS_TABLE, key)
    if not existing:
        return _response(404, {"error": "Trip not found"})

    data = _body(event)
    allowed = (
        "destination", "destinationCoords", "startDate", "endDate",
        "status", "preferences", "priceAlerts",
    )
    updates: dict[str, Any] = {}
    for field in allowed:
        if field in data:
            updates[field] = data[field]

    updates["updatedAt"] = datetime.utcnow().isoformat()
    updated = update_item(TRIPS_TABLE, key, updates)
    return _response(200, _strip_keys(updated or {}))


def delete_trip(event: dict) -> dict:
    user_id = _user_id(event)
    trip_id = event["pathParameters"]["tripId"]
    key = {"PK": f"USER#{user_id}", "SK": f"TRIP#{trip_id}"}

    existing = get_item(TRIPS_TABLE, key)
    if not existing:
        return _response(404, {"error": "Trip not found"})

    delete_item(TRIPS_TABLE, key)
    return _response(200, {"message": "Trip deleted", "tripId": trip_id})


def get_scouts(event: dict) -> dict:
    trip_id = event["pathParameters"]["tripId"]
    items = query_items(SCOUT_RESULTS_TABLE, "PK", f"TRIP#{trip_id}", sk_prefix="SCOUT#")
    return _response(200, [_strip_keys(i) for i in items])


def get_scout_trends(event: dict) -> dict:
    """Return scout results grouped by type for price-over-time charting."""
    trip_id = event["pathParameters"]["tripId"]
    items = query_items(SCOUT_RESULTS_TABLE, "PK", f"TRIP#{trip_id}", sk_prefix="SCOUT#")

    trends: dict[str, list[dict]] = {"flight": [], "hotel": []}
    for item in items:
        entry = {
            "price": item.get("price"),
            "provider": item.get("provider"),
            "scoutedAt": item.get("scoutedAt"),
        }
        result_type = item.get("resultType", "flight")
        trends.setdefault(result_type, []).append(entry)

    return _response(200, trends)


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
    ("POST",   "/trips"):                          create_trip,
    ("GET",    "/trips"):                           list_trips,
    ("GET",    "/trips/{tripId}"):                  get_trip,
    ("PUT",    "/trips/{tripId}"):                  update_trip,
    ("DELETE", "/trips/{tripId}"):                  delete_trip,
    ("GET",    "/trips/{tripId}/scouts"):            get_scouts,
    ("GET",    "/trips/{tripId}/scouts/trends"):     get_scout_trends,
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
