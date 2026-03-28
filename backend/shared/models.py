"""Pydantic data models for Travel Buddy entities."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float
    lng: float


class TripPreferences(BaseModel):
    budget: Optional[float] = None
    interests: list[str] = Field(default_factory=list)
    fitness_needs: list[str] = Field(default_factory=list)
    equipment_prefs: list[str] = Field(default_factory=list)


class PriceAlerts(BaseModel):
    max_flight: Optional[float] = None
    max_hotel_per_night: Optional[float] = None


class Trip(BaseModel):
    trip_id: str
    user_id: str
    destination: str
    destination_coords: Optional[Coordinates] = None
    start_date: str
    end_date: str
    status: str = "planning"
    preferences: TripPreferences = Field(default_factory=TripPreferences)
    price_alerts: PriceAlerts = Field(default_factory=PriceAlerts)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Document(BaseModel):
    doc_id: str
    user_id: str
    trip_id: Optional[str] = None
    s3_key: str
    file_name: str
    parsed_data: Optional[dict] = None
    status: str = "uploaded"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ScoutResult(BaseModel):
    trip_id: str
    result_type: str  # "flight" | "hotel"
    provider: str
    price: float
    currency: str = "USD"
    details: dict = Field(default_factory=dict)
    url: Optional[str] = None
    scouted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
