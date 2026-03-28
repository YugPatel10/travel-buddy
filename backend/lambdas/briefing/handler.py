"""Briefing Lambda — generates daily trip briefings and serves POI data.

Routes handled (via API Gateway proxy integration):
  GET    /trips/{tripId}/briefing     → get_briefing
  POST   /trips/{tripId}/briefing     → generate_briefing
  GET    /trips/{tripId}/pois         → get_pois
  POST   /trips/{tripId}/pois/search  → search_pois
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any


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


def _response(status: int, body: Any) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def _placeholder_briefing(trip_id: str) -> dict:
    """Return placeholder briefing data for stub implementation."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return {
        "tripId": trip_id,
        "date": today,
        "weather": {
            "summary": "Partly cloudy",
            "high": 24,
            "low": 16,
            "unit": "C",
        },
        "itinerary": [
            {"time": "09:00", "activity": "Breakfast at hotel"},
            {"time": "10:30", "activity": "City walking tour"},
            {"time": "13:00", "activity": "Lunch break"},
            {"time": "15:00", "activity": "Museum visit"},
            {"time": "19:00", "activity": "Dinner reservation"},
        ],
        "gymOfTheDay": {
            "name": "FitLife Downtown",
            "address": "123 Main St",
            "rating": 4.5,
            "distance": "0.8 km",
            "hours": "06:00–22:00",
        },
        "localTips": [
            "Carry an umbrella — afternoon showers are common.",
            "The metro is faster than taxis during rush hour.",
        ],
        "alerts": [],
        "generatedAt": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def get_briefing(event: dict) -> dict:
    """GET /trips/{tripId}/briefing — return today's briefing (stub)."""
    _user_id(event)  # validate auth
    trip_id = event["pathParameters"]["tripId"]
    return _response(200, _placeholder_briefing(trip_id))


def generate_briefing(event: dict) -> dict:
    """POST /trips/{tripId}/briefing — generate a briefing on-demand (stub)."""
    _user_id(event)  # validate auth
    trip_id = event["pathParameters"]["tripId"]
    return _response(201, _placeholder_briefing(trip_id))


def get_pois(event: dict) -> dict:
    """GET /trips/{tripId}/pois — return POIs near the trip destination (stub)."""
    _user_id(event)  # validate auth
    trip_id = event["pathParameters"]["tripId"]
    return _response(200, {
        "tripId": trip_id,
        "pois": [],
        "note": "POI data will be available once the Gym Finder agent is integrated.",
    })


def search_pois(event: dict) -> dict:
    """POST /trips/{tripId}/pois/search — search for specific POI types (stub)."""
    _user_id(event)  # validate auth
    trip_id = event["pathParameters"]["tripId"]
    return _response(200, {
        "tripId": trip_id,
        "results": [],
        "note": "POI search will be available once the Google Places tool is integrated.",
    })


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, str], Any] = {
    ("GET",  "/trips/{tripId}/briefing"):    get_briefing,
    ("POST", "/trips/{tripId}/briefing"):    generate_briefing,
    ("GET",  "/trips/{tripId}/pois"):        get_pois,
    ("POST", "/trips/{tripId}/pois/search"): search_pois,
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
        import traceback
        traceback.print_exc()
        return _response(500, {"error": "Internal server error"})
