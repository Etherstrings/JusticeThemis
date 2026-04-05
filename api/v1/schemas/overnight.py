# -*- coding: utf-8 -*-
"""Pydantic schemas for overnight API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OvernightBriefResponse(BaseModel):
    """Latest overnight brief payload."""

    brief_id: str = Field(..., description="Overnight brief id")
    digest_date: str = Field(..., description="Digest date (YYYY-MM-DD)")
    cutoff_time: str = Field(..., description="Digest cutoff time (HH:MM)")
    topline: str = Field(..., description="Topline summary")
    top_events: list[dict[str, Any]] = Field(default_factory=list, description="Ranked top events")
    cross_asset_snapshot: list[dict[str, Any]] = Field(default_factory=list, description="Cross-asset snapshot")
    likely_beneficiaries: list[dict[str, Any]] = Field(default_factory=list, description="Likely beneficiaries")
    likely_pressure_points: list[dict[str, Any]] = Field(default_factory=list, description="Likely pressure points")
    what_may_get_more_expensive: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Potentially more expensive assets or items",
    )
    policy_radar: list[dict[str, Any]] = Field(default_factory=list, description="Policy radar")
    macro_radar: list[dict[str, Any]] = Field(default_factory=list, description="Macro radar")
    sector_transmission: list[dict[str, Any]] = Field(default_factory=list, description="Sector transmission")
    risk_board: list[dict[str, Any]] = Field(default_factory=list, description="Risk board")
    need_confirmation: list[dict[str, Any]] = Field(default_factory=list, description="Items needing confirmation")
    today_watchlist: list[dict[str, Any]] = Field(default_factory=list, description="Today's watchlist")
    primary_sources: list[dict[str, Any]] = Field(default_factory=list, description="Primary sources")
    evidence_links: list[dict[str, Any]] = Field(default_factory=list, description="Evidence links")
    generated_at: str = Field(..., description="Generation timestamp")
    version_no: int = Field(1, description="Payload version")


class OvernightEventResponse(BaseModel):
    """Single overnight event detail payload."""

    event_id: str = Field(..., description="Event id")
    priority_level: str = Field("", description="Priority level")
    core_fact: str = Field("", description="Core fact")
    summary: str = Field("", description="Summary")
    why_it_matters: str = Field("", description="Why it matters")
    confidence: float = Field(0.0, description="Confidence score")


class OvernightBriefHistoryItemResponse(BaseModel):
    """Summary item for persisted overnight brief history."""

    brief_id: str = Field(..., description="Overnight brief id")
    digest_date: str = Field(..., description="Digest date (YYYY-MM-DD)")
    cutoff_time: str = Field(..., description="Digest cutoff time (HH:MM)")
    topline: str = Field(..., description="Topline summary")
    generated_at: str = Field(..., description="Generation timestamp")


class OvernightBriefHistoryResponse(BaseModel):
    """Paginated overnight brief history response."""

    total: int = Field(..., description="Total number of persisted briefs")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Page size")
    items: list[OvernightBriefHistoryItemResponse] = Field(default_factory=list, description="Persisted brief list")
