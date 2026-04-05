# -*- coding: utf-8 -*-
"""Overnight brief API endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query

from api.v1.schemas.overnight import (
    OvernightBriefHistoryItemResponse,
    OvernightBriefHistoryResponse,
    OvernightBriefResponse,
    OvernightEventResponse,
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


@router.get("/history", response_model=OvernightBriefHistoryResponse)
def get_brief_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightBriefHistoryResponse:
    try:
        result = service.list_history(page=page, limit=limit)
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


@router.get("/events/{event_id}", response_model=OvernightEventResponse)
def get_event_detail(
    event_id: str,
    service: OvernightService = Depends(get_overnight_service),
) -> OvernightEventResponse:
    try:
        return OvernightEventResponse.model_validate(service.get_event_detail(event_id))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"Overnight event not found: {exc}",
            },
        )
