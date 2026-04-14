# -*- coding: utf-8 -*-
"""Helpers to build prompt/MMU artifacts for downstream delivery."""

from __future__ import annotations

from typing import Any, Protocol


class DailyAnalysisArtifactProvider(Protocol):
    def get_prompt_bundle(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        """Return one prompt bundle."""

    def get_daily_report(
        self,
        *,
        analysis_date: str | None = None,
        access_tier: str = "free",
        version: int | None = None,
    ) -> dict[str, Any] | None:
        """Return one daily report."""


class HandoffArtifactProvider(Protocol):
    def get_handoff(self, *, limit: int = 20, analysis_date: str | None = None) -> dict[str, Any]:
        """Return one handoff payload."""


class MMUArtifactProvider(Protocol):
    def build_bundle(
        self,
        *,
        handoff: dict[str, Any],
        analysis_report: dict[str, Any] | None = None,
        item_limit: int = 8,
        access_tier: str = "free",
    ) -> dict[str, Any]:
        """Build one staged MMU bundle."""


class PipelineArtifactService:
    def __init__(
        self,
        *,
        daily_analysis_service: DailyAnalysisArtifactProvider,
        handoff_service: HandoffArtifactProvider,
        mmu_handoff_service: MMUArtifactProvider,
    ) -> None:
        self.daily_analysis_service = daily_analysis_service
        self.handoff_service = handoff_service
        self.mmu_handoff_service = mmu_handoff_service

    def build(
        self,
        *,
        analysis_date: str,
        item_limit: int = 8,
        include_daily_analysis_artifacts: bool = True,
        include_mmu_handoff: bool = True,
        mmu_access_tier: str = "premium",
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        if include_daily_analysis_artifacts:
            for access_tier in ("free", "premium"):
                prompt_bundle = self.daily_analysis_service.get_prompt_bundle(
                    analysis_date=analysis_date,
                    access_tier=access_tier,
                )
                if prompt_bundle is None:
                    continue
                artifacts.append(
                    {
                        "artifact_type": f"daily_{access_tier}_prompt",
                        "content_type": "application/json",
                        "filename_hint": f"daily-{access_tier}-prompt-{analysis_date}.json",
                        "payload": prompt_bundle,
                    }
                )

        if include_mmu_handoff:
            analysis_report = self.daily_analysis_service.get_daily_report(
                analysis_date=analysis_date,
                access_tier=mmu_access_tier,
            )
            handoff = self.handoff_service.get_handoff(
                limit=max(20, int(item_limit)),
                analysis_date=analysis_date,
            )
            artifacts.append(
                {
                    "artifact_type": "mmu_handoff",
                    "content_type": "application/json",
                    "filename_hint": f"mmu-handoff-{analysis_date}.json",
                    "payload": self.mmu_handoff_service.build_bundle(
                        handoff=handoff,
                        analysis_report=analysis_report,
                        item_limit=max(1, int(item_limit)),
                        access_tier=mmu_access_tier,
                    ),
                }
            )
        return artifacts
