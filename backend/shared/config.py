"""Environment configuration for Lambda functions."""

from __future__ import annotations

import os


def get_env(name: str, default: str = "") -> str:
    """Read an environment variable with an optional default."""
    return os.environ.get(name, default)


# Table names
TRIPS_TABLE = get_env("TRIPS_TABLE", "TravelBuddy-Trips")
DOCUMENTS_TABLE = get_env("DOCUMENTS_TABLE", "TravelBuddy-Documents")
SCOUT_RESULTS_TABLE = get_env("SCOUT_RESULTS_TABLE", "TravelBuddy-ScoutResults")
AGENT_RUNS_TABLE = get_env("AGENT_RUNS_TABLE", "TravelBuddy-AgentRuns")

# S3
UPLOAD_BUCKET = get_env("UPLOAD_BUCKET", "travel-buddy-uploads")

# External service keys (resolved from Secrets Manager at runtime)
PINECONE_API_KEY_SECRET = get_env("PINECONE_API_KEY_SECRET")
FIRECRAWL_API_KEY_SECRET = get_env("FIRECRAWL_API_KEY_SECRET")
TAVILY_API_KEY_SECRET = get_env("TAVILY_API_KEY_SECRET")
GOOGLE_PLACES_API_KEY_SECRET = get_env("GOOGLE_PLACES_API_KEY_SECRET")
OPENWEATHERMAP_API_KEY_SECRET = get_env("OPENWEATHERMAP_API_KEY_SECRET")
