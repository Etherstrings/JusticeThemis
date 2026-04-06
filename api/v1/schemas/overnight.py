# -*- coding: utf-8 -*-
"""Pydantic schemas for overnight API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OvernightWatchItemResponse(BaseModel):
    """Structured watch item for the opening board."""

    watch_id: str = Field(..., description="Stable watch item id")
    bucket_key: str = Field(..., description="Owning watch bucket key")
    label: str = Field(..., description="Short action label")
    event_id: str | None = Field(None, description="Linked overnight event id when available")
    core_fact: str = Field(..., description="Core fact to keep watching")
    priority_level: str = Field("", description="Priority level of the linked event")
    confidence: float = Field(0.0, description="Confidence score of the linked event")
    trigger: str = Field("", description="What should trigger the user's attention next")
    action: str = Field("", description="Recommended action for the user")
    market_reaction: str = Field("", description="Known first-priced object or market reaction")


class OvernightWatchBucketResponse(BaseModel):
    """Bucket of related opening-board watch items."""

    bucket_key: str = Field(..., description="Stable bucket key")
    title: str = Field(..., description="Bucket display title")
    summary: str = Field("", description="Bucket summary")
    items: list[OvernightWatchItemResponse] = Field(default_factory=list, description="Watch items in this bucket")


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
    today_watchlist: list[OvernightWatchBucketResponse] = Field(default_factory=list, description="Today's watchlist")
    primary_sources: list[dict[str, Any]] = Field(default_factory=list, description="Primary sources")
    evidence_links: list[dict[str, Any]] = Field(default_factory=list, description="Evidence links")
    generated_at: str = Field(..., description="Generation timestamp")
    version_no: int = Field(1, description="Payload version")


class OvernightBriefDeltaEventResponse(BaseModel):
    """Single event delta item between two adjacent briefs."""

    event_key: str = Field(..., description="Stable event aggregation key")
    core_fact: str = Field(..., description="Shared core fact headline")
    current_event_id: str | None = Field(None, description="Event id inside the current brief")
    previous_event_id: str | None = Field(None, description="Event id inside the previous brief")
    current_priority_level: str = Field("", description="Priority level in the current brief")
    previous_priority_level: str = Field("", description="Priority level in the previous brief")
    current_confidence: float = Field(0.0, description="Confidence in the current brief")
    previous_confidence: float = Field(0.0, description="Confidence in the previous brief")
    delta_type: str = Field(..., description="Change type such as new/intensified/steady/cooling/dropped")
    delta_summary: str = Field("", description="Human-readable delta summary")


class OvernightBriefDeltaResponse(BaseModel):
    """Structured comparison between a brief and its previous brief."""

    brief_id: str = Field(..., description="Current brief id")
    digest_date: str = Field(..., description="Current brief digest date")
    previous_brief_id: str | None = Field(None, description="Previous brief id if available")
    previous_digest_date: str | None = Field(None, description="Previous brief digest date if available")
    summary: str = Field("", description="High-level comparison summary")
    new_events: list[OvernightBriefDeltaEventResponse] = Field(default_factory=list, description="New events")
    intensified_events: list[OvernightBriefDeltaEventResponse] = Field(default_factory=list, description="Events that intensified")
    steady_events: list[OvernightBriefDeltaEventResponse] = Field(default_factory=list, description="Events that stayed broadly unchanged")
    cooling_events: list[OvernightBriefDeltaEventResponse] = Field(default_factory=list, description="Events that cooled")
    dropped_events: list[OvernightBriefDeltaEventResponse] = Field(default_factory=list, description="Events that dropped out")


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


class OvernightEventHistoryOccurrenceResponse(BaseModel):
    """Single historical occurrence of an event across briefs."""

    brief_id: str = Field(..., description="Brief containing the event")
    digest_date: str = Field(..., description="Digest date of the brief")
    event_id: str = Field(..., description="Event id inside the brief")
    priority_level: str = Field("", description="Priority level at that time")
    confidence: float = Field(0.0, description="Confidence score at that time")


class OvernightEventHistoryItemResponse(BaseModel):
    """Aggregated event history item."""

    event_key: str = Field(..., description="Stable aggregation key for the event")
    core_fact: str = Field(..., description="Shared core fact headline")
    occurrence_count: int = Field(..., description="Number of briefs containing the event")
    latest_brief_id: str | None = Field(None, description="Most recent brief containing the event")
    latest_digest_date: str | None = Field(None, description="Most recent digest date containing the event")
    latest_event_id: str | None = Field(None, description="Event id inside the most recent brief")
    latest_priority_level: str = Field("", description="Priority level in the most recent brief")
    average_confidence: float = Field(0.0, description="Average confidence across occurrences")
    occurrences: list[OvernightEventHistoryOccurrenceResponse] = Field(
        default_factory=list,
        description="Recent historical occurrences for this event",
    )


class OvernightEventHistoryResponse(BaseModel):
    """Paginated aggregated event history response."""

    total: int = Field(..., description="Total number of grouped events")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Page size")
    items: list[OvernightEventHistoryItemResponse] = Field(default_factory=list, description="Aggregated event groups")


class OvernightTopicHistoryOccurrenceResponse(BaseModel):
    """Single historical occurrence of a topic across briefs."""

    brief_id: str = Field(..., description="Brief containing the topic")
    digest_date: str = Field(..., description="Digest date of the brief")
    item_count: int = Field(..., description="Number of cards under this topic in the brief")


class OvernightTopicHistoryItemResponse(BaseModel):
    """Aggregated topic history item."""

    topic_key: str = Field(..., description="Topic key")
    title: str = Field(..., description="Topic display title")
    occurrence_count: int = Field(..., description="Number of briefs containing this topic")
    total_item_count: int = Field(..., description="Total cards seen across all occurrences")
    latest_brief_id: str | None = Field(None, description="Most recent brief containing the topic")
    latest_digest_date: str | None = Field(None, description="Most recent digest date containing the topic")
    latest_item_count: int = Field(0, description="Number of cards in the most recent brief")
    recent_briefs: list[OvernightTopicHistoryOccurrenceResponse] = Field(
        default_factory=list,
        description="Recent briefs containing the topic",
    )


class OvernightTopicHistoryResponse(BaseModel):
    """Paginated aggregated topic history response."""

    total: int = Field(..., description="Total number of grouped topics")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Page size")
    items: list[OvernightTopicHistoryItemResponse] = Field(default_factory=list, description="Aggregated topic groups")


class OvernightSourceResponse(BaseModel):
    """Catalog entry for a configured overnight source."""

    source_id: str = Field(..., description="Source id")
    display_name: str = Field(..., description="Display name")
    organization_type: str = Field(..., description="Organization type")
    source_class: str = Field(..., description="Source class")
    entry_type: str = Field(..., description="Collection entry type")
    entry_urls: list[str] = Field(default_factory=list, description="Collection entry URLs")
    priority: int = Field(..., description="Priority weight")
    poll_interval_seconds: int = Field(..., description="Suggested poll interval in seconds")
    is_mission_critical: bool = Field(False, description="Whether the source is mission critical")
    is_enabled: bool = Field(False, description="Whether the source is currently enabled by whitelist settings")


class OvernightSourceListResponse(BaseModel):
    """Overnight source catalog response."""

    total: int = Field(..., description="Total number of known sources")
    mission_critical: int = Field(..., description="Number of mission critical sources")
    items: list[OvernightSourceResponse] = Field(default_factory=list, description="Registered overnight sources")


class OvernightSourceHealthResponse(BaseModel):
    """Operational health of source coverage."""

    total_sources: int = Field(..., description="Total registered sources")
    mission_critical_sources: int = Field(..., description="Mission critical sources")
    whitelisted_sources: int = Field(..., description="Sources currently enabled by whitelist settings")


class OvernightPipelineHealthResponse(BaseModel):
    """Persistence and latest-brief status."""

    brief_count: int = Field(..., description="Number of persisted briefs")
    latest_brief_id: str | None = Field(None, description="Most recent persisted brief id")
    latest_digest_date: str | None = Field(None, description="Most recent persisted digest date")
    latest_generated_at: str | None = Field(None, description="Most recent persisted generation time")


class OvernightContentQualityResponse(BaseModel):
    """Derived quality signals from the latest persisted brief."""

    top_event_count: int = Field(..., description="Number of top events in the latest brief")
    average_confidence: float = Field(..., description="Average confidence across top events")
    events_needing_confirmation: int = Field(..., description="Number of low-confidence events")
    events_with_primary_sources: int = Field(..., description="Top events carrying primary source links")
    events_without_primary_sources: int = Field(..., description="Top events missing primary source links")
    duplicate_core_fact_count: int = Field(..., description="Duplicate core-fact count across top events")
    minimum_evidence_gate_passed: bool = Field(..., description="Whether all top events carry primary evidence links")
    duplication_gate_passed: bool = Field(..., description="Whether duplicate core facts were avoided")


class OvernightDeliveryHealthResponse(BaseModel):
    """Notification and delivery capability status."""

    notification_available: bool = Field(..., description="Whether any delivery channel is available")
    configured_channels: list[str] = Field(default_factory=list, description="Configured delivery channel ids")
    channel_names: str = Field("", description="Configured delivery channel display names")
    overnight_brief_enabled: bool = Field(..., description="Whether overnight brief mode is enabled")


class OvernightHealthResponse(BaseModel):
    """Aggregated overnight health summary."""

    source_health: OvernightSourceHealthResponse
    pipeline_health: OvernightPipelineHealthResponse
    content_quality: OvernightContentQualityResponse
    delivery_health: OvernightDeliveryHealthResponse


class OvernightFeedbackCreateRequest(BaseModel):
    """Create a feedback item for a brief or event."""

    target_type: str = Field(..., description="Feedback target type: brief or event")
    target_id: str = Field(..., description="Target identifier")
    brief_id: str | None = Field(None, description="Associated brief id")
    event_id: str | None = Field(None, description="Associated event id")
    feedback_type: str = Field(..., description="Feedback category")
    comment: str = Field("", description="Optional free-form comment")


class OvernightFeedbackResponse(BaseModel):
    """Stored overnight feedback item."""

    feedback_id: int = Field(..., description="Feedback primary key")
    target_type: str = Field(..., description="Feedback target type")
    target_id: str = Field(..., description="Feedback target id")
    brief_id: str | None = Field(None, description="Associated brief id")
    event_id: str | None = Field(None, description="Associated event id")
    feedback_type: str = Field(..., description="Feedback category")
    comment: str = Field("", description="Free-form comment")
    status: str = Field(..., description="Review queue status")
    created_at: str | None = Field(None, description="Creation timestamp")


class OvernightFeedbackListResponse(BaseModel):
    """Paginated overnight feedback queue response."""

    total: int = Field(..., description="Total feedback items matching the filters")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Page size")
    items: list[OvernightFeedbackResponse] = Field(default_factory=list, description="Feedback queue items")


class OvernightFeedbackUpdateRequest(BaseModel):
    """Update a feedback item's review status."""

    status: str = Field(..., description="Next review status")
