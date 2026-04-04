# -*- coding: utf-8 -*-
"""Structured analysis packets for overnight intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyAnalystOutput:
    event_id: str
    policy_status: str
    issuing_authority: str
    immediate_implications: list[str]
    confidence: float


@dataclass(frozen=True)
class SkepticalReviewPacket:
    event_id: str
    challenge_points: list[str]
    downgraded_confidence: float


__all__ = [
    "PolicyAnalystOutput",
    "SkepticalReviewPacket",
]
