"""Tests for shared utilities: models, config, and dynamo helpers."""

from __future__ import annotations

import os
import sys

import pytest

# Ensure shared package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── models tests ──────────────────────────────────────────────────────────


class TestModels:
    """Validate Pydantic models match the DynamoDB schema from the design doc."""

    def test_trip_defaults(self):
        from shared.models import Trip

        trip = Trip(
            trip_id="01J1",
            user_id="u1",
            destination="Tokyo",
            start_date="2025-08-01",
            end_date="2025-08-10",
        )
        assert trip.status == "planning"
        assert trip.preferences.budget is None
        assert trip.preferences.interests == []
        assert trip.price_alerts.max_flight is None
        assert trip.created_at  # auto-populated
        assert trip.updated_at

    def test_trip_full(self):
        from shared.models import Coordinates, PriceAlerts, Trip, TripPreferences

        trip = Trip(
            trip_id="01J2",
            user_id="u2",
            destination="Berlin",
            destination_coords=Coordinates(lat=52.52, lng=13.405),
            start_date="2025-09-01",
            end_date="2025-09-07",
            status="active",
            preferences=TripPreferences(
                budget=3000.0,
                interests=["museums", "food"],
                fitness_needs=["gym"],
                equipment_prefs=["squat rack"],
            ),
            price_alerts=PriceAlerts(max_flight=600.0, max_hotel_per_night=150.0),
        )
        assert trip.destination_coords.lat == 52.52
        assert trip.preferences.budget == 3000.0
        assert trip.price_alerts.max_flight == 600.0

    def test_document_defaults(self):
        from shared.models import Document

        doc = Document(
            doc_id="d1",
            user_id="u1",
            s3_key="uploads/u1/d1/booking.pdf",
            file_name="booking.pdf",
        )
        assert doc.status == "uploaded"
        assert doc.trip_id is None
        assert doc.parsed_data is None

    def test_scout_result_with_ttl(self):
        from shared.models import ScoutResult

        sr = ScoutResult(
            trip_id="t1",
            result_type="flight",
            provider="Kayak",
            price=450.0,
            ttl=1756684800,
        )
        assert sr.currency == "USD"
        assert sr.ttl == 1756684800
        assert sr.details == {}

    def test_scout_result_no_ttl(self):
        from shared.models import ScoutResult

        sr = ScoutResult(
            trip_id="t1",
            result_type="hotel",
            provider="Booking.com",
            price=120.0,
        )
        assert sr.ttl is None

    def test_agent_run_defaults(self):
        from shared.models import AgentRun

        run = AgentRun(
            trip_id="t1",
            run_id="r1",
            agent_type="scout",
        )
        assert run.status == "running"
        assert run.input == {}
        assert run.output == {}
        assert run.decisions == []
        assert run.completed_at is None
        assert run.started_at

    def test_agent_run_with_decisions(self):
        from shared.models import AgentDecision, AgentRun

        run = AgentRun(
            trip_id="t1",
            run_id="r2",
            agent_type="parser",
            status="completed",
            decisions=[
                AgentDecision(node="extract", condition="has_text", result="true"),
                AgentDecision(node="embed", condition="text_length>0", result="true"),
            ],
            completed_at="2025-08-01T12:00:00",
        )
        assert len(run.decisions) == 2
        assert run.decisions[0].node == "extract"
        assert run.status == "completed"


# ── config tests ──────────────────────────────────────────────────────────


class TestConfig:
    """Validate config reads env vars with correct defaults."""

    def test_defaults(self):
        from shared.config import (
            AGENT_RUNS_TABLE,
            AWS_REGION,
            DOCUMENTS_TABLE,
            PINECONE_INDEX_NAME,
            SCOUT_RESULTS_TABLE,
            TRIPS_TABLE,
            UPLOAD_BUCKET,
        )

        assert TRIPS_TABLE == "TravelBuddy-Trips"
        assert DOCUMENTS_TABLE == "TravelBuddy-Documents"
        assert SCOUT_RESULTS_TABLE == "TravelBuddy-ScoutResults"
        assert AGENT_RUNS_TABLE == "TravelBuddy-AgentRuns"
        assert UPLOAD_BUCKET == "travel-buddy-uploads"
        assert AWS_REGION == "us-east-1"
        assert PINECONE_INDEX_NAME == "travel-buddy"

    def test_get_env_with_override(self, monkeypatch):
        monkeypatch.setenv("TRIPS_TABLE", "CustomTrips")
        # Re-import to pick up the env change
        from shared.config import get_env

        assert get_env("TRIPS_TABLE", "TravelBuddy-Trips") == "CustomTrips"

    def test_get_env_missing_returns_default(self):
        from shared.config import get_env

        assert get_env("NONEXISTENT_VAR_XYZ", "fallback") == "fallback"


# ── dynamo tests ──────────────────────────────────────────────────────────



@pytest.fixture
def dynamo_table(monkeypatch):
    """Create a moto DynamoDB table for testing."""
    import boto3
    from moto import mock_aws

    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")

        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="TestTable",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield "TestTable"


class TestDynamo:
    """Test DynamoDB helper functions against moto mock."""

    def test_put_and_get_item(self, dynamo_table):
        from shared.dynamo import get_item, put_item

        item = {"PK": "USER#u1", "SK": "TRIP#t1", "destination": "Tokyo"}
        put_item(dynamo_table, item)

        result = get_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1"})
        assert result is not None
        assert result["destination"] == "Tokyo"

    def test_get_item_missing(self, dynamo_table):
        from shared.dynamo import get_item

        result = get_item(dynamo_table, {"PK": "USER#none", "SK": "TRIP#none"})
        assert result is None

    def test_query_items(self, dynamo_table):
        from shared.dynamo import put_item, query_items

        put_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#a", "name": "Trip A"})
        put_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#b", "name": "Trip B"})
        put_item(dynamo_table, {"PK": "USER#u1", "SK": "DOC#d1", "name": "Doc 1"})

        trips = query_items(dynamo_table, "PK", "USER#u1", sk_prefix="TRIP#")
        assert len(trips) == 2

    def test_query_items_descending(self, dynamo_table):
        from shared.dynamo import put_item, query_items

        put_item(dynamo_table, {"PK": "T#1", "SK": "SCOUT#2025-01-01#flight"})
        put_item(dynamo_table, {"PK": "T#1", "SK": "SCOUT#2025-06-01#flight"})

        results = query_items(dynamo_table, "PK", "T#1", sk_prefix="SCOUT#", scan_forward=False)
        assert len(results) == 2
        # Descending: newest first
        assert results[0]["SK"] > results[1]["SK"]

    def test_query_items_with_limit(self, dynamo_table):
        from shared.dynamo import put_item, query_items

        for i in range(5):
            put_item(dynamo_table, {"PK": "USER#u1", "SK": f"TRIP#{i}"})

        results = query_items(dynamo_table, "PK", "USER#u1", sk_prefix="TRIP#", limit=2)
        assert len(results) == 2

    def test_update_item(self, dynamo_table):
        from shared.dynamo import put_item, update_item

        put_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1", "status": "planning"})

        updated = update_item(
            dynamo_table,
            {"PK": "USER#u1", "SK": "TRIP#t1"},
            {"status": "active"},
        )
        assert updated is not None
        assert updated["status"] == "active"

    def test_update_item_empty_updates(self, dynamo_table):
        from shared.dynamo import get_item, put_item, update_item

        put_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1", "status": "planning"})

        result = update_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1"}, {})
        assert result is not None
        assert result["status"] == "planning"

    def test_delete_item(self, dynamo_table):
        from shared.dynamo import delete_item, get_item, put_item

        put_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1"})
        delete_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1"})

        result = get_item(dynamo_table, {"PK": "USER#u1", "SK": "TRIP#t1"})
        assert result is None

    def test_batch_write_items(self, dynamo_table):
        from shared.dynamo import batch_write_items, query_items

        items = [
            {"PK": "TRIP#t1", "SK": f"RUN#r{i}", "agentType": "scout"}
            for i in range(10)
        ]
        batch_write_items(dynamo_table, items)

        results = query_items(dynamo_table, "PK", "TRIP#t1", sk_prefix="RUN#")
        assert len(results) == 10
