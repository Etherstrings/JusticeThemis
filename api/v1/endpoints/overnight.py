# -*- coding: utf-8 -*-
"""Overnight brief API endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query

from api.v1.schemas.overnight import (
    OvernightBriefDeltaEventResponse,
    OvernightBriefDeltaResponse,
    OvernightBriefHistoryItemResponse,
    OvernightBriefHistoryResponse,
    OvernightBriefResponse,
    OvernightEventResponse,
    OvernightEventHistoryItemResponse,
    OvernightEventHistoryOccurrenceResponse,
    OvernightEventHistoryResponse,
    OvernightFeedbackCreateRequest,
    OvernightFeedbackListResponse,
    OvernightFeedbackResponse,
    OvernightFeedbackUpdateRequest,
    OvernightHealthResponse,
    OvernightSourceListResponse,
    OvernightSourceItemListResponse,
    OvernightSourceItemResponse,
    OvernightSourceRefreshResponse,
    OvernightSourceResponse,
    OvernightTopicHistoryItemResponse,
    OvernightTopicHistoryOccurrenceResponse,
    OvernightTopicHistoryResponse,
)
from src.services.overnight_service import OvernightService

router = APIRouter()


def get_overnight_service() -> OvernightService:
    """Dependency provider for overnight service."""
    return OvernightService()


@router.get("/brief/latest", response_model=OvernightBriefResponse)
def get_latest_brief(
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefResponse:
    try:
        brief = service.get_latest_brief()
        return OvernightBriefResponse.model_validate(asdict(brief))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/brief/latest/delta", response_model=OvernightBriefDeltaResponse)
def get_latest_brief_delta(
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefDeltaResponse:
    try:
        result = service.get_brief_delta()
        return OvernightBriefDeltaResponse(
            brief_id=str(result.get("brief_id", "")),
            digest_date=str(result.get("digest_date", "")),
            previous_brief_id=result.get("previous_brief_id"),
            previous_digest_date=result.get("previous_digest_date"),
            summary=str(result.get("summary", "")),
            new_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("new_events", [])
            ],
            intensified_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("intensified_events", [])
            ],
            steady_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("steady_events", [])
            ],
            cooling_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("cooling_events", [])
            ],
            dropped_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("dropped_events", [])
            ],
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/briefs/{brief_id}", response_model=OvernightBriefResponse)
def get_brief_by_id(
    brief_id: str,
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefResponse:
    try:
        brief = service.get_brief_by_id(brief_id)
        return OvernightBriefResponse.model_validate(asdict(brief))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/briefs/{brief_id}/delta", response_model=OvernightBriefDeltaResponse)
def get_brief_delta_by_id(
    brief_id: str,
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefDeltaResponse:
    try:
        result = service.get_brief_delta(brief_id)
        return OvernightBriefDeltaResponse(
            brief_id=str(result.get("brief_id", "")),
            digest_date=str(result.get("digest_date", "")),
            previous_brief_id=result.get("previous_brief_id"),
            previous_digest_date=result.get("previous_digest_date"),
            summary=str(result.get("summary", "")),
            new_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("new_events", [])
            ],
            intensified_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("intensified_events", [])
            ],
            steady_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("steady_events", [])
            ],
            cooling_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("cooling_events", [])
            ],
            dropped_events=[
                OvernightBriefDeltaEventResponse.model_validate(item)
                for item in result.get("dropped_events", [])
            ],
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/history", response_model=OvernightBriefHistoryResponse)
def get_brief_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    q: str | None = Query(None, description="Optional free-text search query"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefHistoryResponse:
    try:
        result = service.list_history(page=page, limit=limit, q=q)
        items = [
            OvernightBriefHistoryItemResponse.model_validate(item)
            for item in result.get("items", [])
        ]
        return OvernightBriefHistoryResponse(
            total=int(result.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/history/events", response_model=OvernightEventHistoryResponse)
def get_event_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    q: str | None = Query(None, description="Optional free-text search query"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightEventHistoryResponse:
    try:
        result = service.list_event_history(page=page, limit=limit, q=q)
        items = []
        for item in result.get("items", []):
            occurrences = [
                OvernightEventHistoryOccurrenceResponse.model_validate(occurrence)
                for occurrence in item.get("occurrences", [])
            ]
            items.append(
                OvernightEventHistoryItemResponse.model_validate(
                    {
                        **item,
                        "occurrences": occurrences,
                    }
                )
            )
        return OvernightEventHistoryResponse(
            total=int(result.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/history/topics", response_model=OvernightTopicHistoryResponse)
def get_topic_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    q: str | None = Query(None, description="Optional free-text search query"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightTopicHistoryResponse:
    try:
        result = service.list_topic_history(page=page, limit=limit, q=q)
        items = []
        for item in result.get("items", []):
            occurrences = [
                OvernightTopicHistoryOccurrenceResponse.model_validate(occurrence)
                for occurrence in item.get("recent_briefs", [])
            ]
            items.append(
                OvernightTopicHistoryItemResponse.model_validate(
                    {
                        **item,
                        "recent_briefs": occurrences,
                    }
                )
            )
        return OvernightTopicHistoryResponse(
            total=int(result.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )


@router.get("/events/{event_id}", response_model=OvernightEventResponse)
def get_event_detail(
    event_id: str,
    brief_id: str | None = Query(None, description="Optional brief id override for historical event details"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightEventResponse:
    try:
        return OvernightEventResponse.model_validate(service.get_event_detail(event_id, brief_id=brief_id))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Overnight event not found: {exc}",
            },
        )


@router.get("/sources", response_model=OvernightSourceListResponse)
def get_sources(
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightSourceListResponse:
    result = service.list_sources()
    items = [
        OvernightSourceResponse.model_validate(item)
        for item in result.get("items", [])
    ]
    return OvernightSourceListResponse(
        total=int(result.get("total", 0)),
        mission_critical=int(result.get("mission_critical", 0)),
        items=items,
    )


@router.get("/source-items", response_model=OvernightSourceItemListResponse)
def get_recent_source_items(
    limit: int = Query(20, ge=1, le=100, description="Number of recent source items to return"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightSourceItemListResponse:
    result = service.list_recent_source_items(limit=limit)
    items = [
        OvernightSourceItemResponse.model_validate(item)
        for item in result.get("items", [])
    ]
    return OvernightSourceItemListResponse(
        total=int(result.get("total", 0)),
        items=items,
    )


@router.post("/source-items/refresh", response_model=OvernightSourceRefreshResponse)
def refresh_source_items(
    limit_per_source: int = Query(2, ge=1, le=5, description="Max captured items per source"),
    max_sources: int = Query(6, ge=1, le=20, description="Max sources to visit in one refresh"),
    recent_limit: int = Query(12, ge=1, le=100, description="How many recent items to return after refresh"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightSourceRefreshResponse:
    result = service.refresh_source_items(
        limit_per_source=limit_per_source,
        max_sources=max_sources,
        recent_limit=recent_limit,
    )
    items = [
        OvernightSourceItemResponse.model_validate(item)
        for item in result.get("items", [])
    ]
    return OvernightSourceRefreshResponse(
        collected_sources=int(result.get("collected_sources", 0)),
        collected_items=int(result.get("collected_items", 0)),
        total=int(result.get("total", 0)),
        items=items,
    )


@router.get("/health", response_model=OvernightHealthResponse)
def get_health(
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightHealthResponse:
    return OvernightHealthResponse.model_validate(service.get_health_summary())


@router.post("/feedback", response_model=OvernightFeedbackResponse)
def submit_feedback(
    payload: OvernightFeedbackCreateRequest,
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightFeedbackResponse:
    try:
        return OvernightFeedbackResponse.model_validate(
            service.submit_feedback(
                target_type=payload.target_type,
                target_id=payload.target_id,
                brief_id=payload.brief_id,
                event_id=payload.event_id,
                feedback_type=payload.feedback_type,
                comment=payload.comment,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )


@router.get("/feedback", response_model=OvernightFeedbackListResponse)
def get_feedback_queue(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    target_type: str | None = Query(None, description="Optional target type filter"),
    status: str | None = Query(None, description="Optional feedback status filter"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightFeedbackListResponse:
    try:
        result = service.list_feedback(
            page=page,
            limit=limit,
            target_type=target_type,
            status=status,
        )
        items = [
            OvernightFeedbackResponse.model_validate(item)
            for item in result.get("items", [])
        ]
        return OvernightFeedbackListResponse(
            total=int(result.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )


@router.patch("/feedback/{feedback_id}", response_model=OvernightFeedbackResponse)
def update_feedback_status(
    feedback_id: int,
    payload: OvernightFeedbackUpdateRequest,
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightFeedbackResponse:
    try:
        return OvernightFeedbackResponse.model_validate(
            service.update_feedback_status(
                feedback_id,
                status=payload.status,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": str(exc),
            },
        )
