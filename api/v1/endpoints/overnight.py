# -*- coding: utf-8 -*-
"""Overnight brief API endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from api.v1.schemas.overnight import OvernightBriefResponse, OvernightEventResponse
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
