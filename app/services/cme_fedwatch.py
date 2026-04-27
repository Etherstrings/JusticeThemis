# -*- coding: utf-8 -*-
"""CME FedWatch implied Fed path signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from typing import Any

import requests


logger = logging.getLogger(__name__)

_URL = "https://www.cmegroup.com/services/fed-funds-target/fed-funds-target.json"


def cme_fedwatch_enabled_from_env() -> bool:
    raw_value = str(os.environ.get("CME_FEDWATCH_ENABLED", "true")).strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class FedRateProb:
    target_low: float
    target_high: float
    probability: float


@dataclass(frozen=True)
class FedMeetingProbability:
    meeting_date: str
    current_target_low: float
    current_target_high: float
    probabilities: tuple[FedRateProb, ...]


class CMEFedWatchSignalService:
    PROVIDER_NAME = "CME FedWatch"
    PROVIDER_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        enabled: bool = True,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.session = session or requests.Session()
        self.enabled = bool(enabled)
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    @classmethod
    def from_environment(cls) -> "CMEFedWatchSignalService":
        return cls(enabled=cme_fedwatch_enabled_from_env())

    def collect(
        self,
        *,
        analysis_date: str,
        market_date: str,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del previous_snapshot
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        base_payload = {
            "provider_name": self.PROVIDER_NAME,
            "provider_url": self.PROVIDER_URL,
            "analysis_date": str(analysis_date or "").strip(),
            "market_date": str(market_date or "").strip(),
            "generated_at": generated_at,
            "meetings": [],
            "meeting_count": 0,
        }
        if not self.enabled:
            return {**base_payload, "status": "disabled", "status_reason": "disabled_by_env"}
        try:
            meetings = self.get_probabilities()
        except requests.HTTPError as exc:
            status, status_reason = self._classify_http_error(exc)
            logger.warning("Failed to fetch CME FedWatch probabilities: %s", exc)
            return {
                **base_payload,
                "status": status,
                "status_reason": status_reason,
                "error": str(exc),
            }
        except Exception as exc:
            logger.warning("Failed to fetch CME FedWatch probabilities: %s", exc)
            return {
                **base_payload,
                "status": "error",
                "status_reason": "fetch_failed",
                "error": str(exc),
            }
        serialized = [self._serialize_meeting(meeting) for meeting in meetings[:3]]
        headline = self._headline(serialized[0]) if serialized else ""
        return {
            **base_payload,
            "status": "ready" if serialized else "empty",
            "status_reason": "ok" if serialized else "no_meetings",
            "meetings": serialized,
            "meeting_count": len(serialized),
            "headline": headline,
        }

    def get_probabilities(self) -> list[FedMeetingProbability]:
        response = self.session.get(
            _URL,
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": "overnight-news-handoff/1.0",
            },
        )
        response.raise_for_status()
        data = response.json()
        meetings_raw = self._extract_meetings(data)
        if meetings_raw is None:
            raise RuntimeError("cannot locate CME FedWatch meetings data")
        results: list[FedMeetingProbability] = []
        for meeting in meetings_raw:
            parsed = self._parse_meeting(meeting)
            if parsed is not None:
                results.append(parsed)
        return results

    def _serialize_meeting(self, meeting: FedMeetingProbability) -> dict[str, Any]:
        probabilities = sorted(list(meeting.probabilities), key=lambda item: item.probability, reverse=True)
        current_mid = (meeting.current_target_low + meeting.current_target_high) / 2.0
        top_band = probabilities[0] if probabilities else None
        cut_prob = round(
            sum(prob.probability for prob in probabilities if ((prob.target_low + prob.target_high) / 2.0) < current_mid) * 100.0,
            2,
        )
        hold_prob = round(
            sum(prob.probability for prob in probabilities if ((prob.target_low + prob.target_high) / 2.0) == current_mid) * 100.0,
            2,
        )
        hike_prob = round(
            sum(prob.probability for prob in probabilities if ((prob.target_low + prob.target_high) / 2.0) > current_mid) * 100.0,
            2,
        )
        return {
            "meeting_date": meeting.meeting_date,
            "current_target_range": [round(meeting.current_target_low * 100.0, 2), round(meeting.current_target_high * 100.0, 2)],
            "top_target_range": (
                [round(top_band.target_low * 100.0, 2), round(top_band.target_high * 100.0, 2)]
                if top_band is not None
                else None
            ),
            "top_probability": round(top_band.probability * 100.0, 2) if top_band is not None else None,
            "cut_probability": cut_prob,
            "hold_probability": hold_prob,
            "hike_probability": hike_prob,
            "probabilities": [
                {
                    "target_low": round(prob.target_low * 100.0, 2),
                    "target_high": round(prob.target_high * 100.0, 2),
                    "probability": round(prob.probability * 100.0, 2),
                }
                for prob in probabilities
            ],
        }

    def _headline(self, meeting: dict[str, Any]) -> str:
        meeting_date = str(meeting.get("meeting_date", "")).strip()
        cut_prob = meeting.get("cut_probability")
        hold_prob = meeting.get("hold_probability")
        hike_prob = meeting.get("hike_probability")
        return f"下次议息日 {meeting_date}：降息 {cut_prob:.1f}% / 按兵不动 {hold_prob:.1f}% / 加息 {hike_prob:.1f}%"

    def _extract_meetings(self, data: object) -> list[object] | None:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("meetings", "Meetings", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            if "meetingDate" in data or "meeting_date" in data:
                return [data]
        return None

    def _parse_meeting(self, meeting: object) -> FedMeetingProbability | None:
        if not isinstance(meeting, dict):
            return None
        meeting_date = str(meeting.get("meetingDate") or meeting.get("meeting_date") or "").strip()
        if not meeting_date:
            return None
        current_range = self._parse_target_range(str(meeting.get("currentTarget") or meeting.get("current_target") or ""))
        if current_range is None:
            return None
        probs_raw = meeting.get("probabilities") or meeting.get("Probabilities") or {}
        probabilities: list[FedRateProb] = []
        if isinstance(probs_raw, dict):
            for range_key, prob_val in probs_raw.items():
                band = self._parse_target_range(str(range_key))
                prob = self._to_float(prob_val)
                if band is None or prob is None or prob == 0.0:
                    continue
                probabilities.append(FedRateProb(target_low=band[0], target_high=band[1], probability=prob / 100.0))
        elif isinstance(probs_raw, list):
            for item in probs_raw:
                if not isinstance(item, dict):
                    continue
                band = self._parse_target_range(str(item.get("range") or item.get("target") or ""))
                prob = self._to_float(item.get("probability") or item.get("prob"))
                if band is None or prob is None or prob == 0.0:
                    continue
                probabilities.append(FedRateProb(target_low=band[0], target_high=band[1], probability=prob / 100.0))
        return FedMeetingProbability(
            meeting_date=meeting_date,
            current_target_low=current_range[0],
            current_target_high=current_range[1],
            probabilities=tuple(probabilities),
        )

    def _parse_target_range(self, raw: str) -> tuple[float, float] | None:
        parts = raw.split("-")
        if len(parts) != 2:
            return None
        low = self._to_float(parts[0])
        high = self._to_float(parts[1])
        if low is None or high is None:
            return None
        return low / 100.0, high / 100.0

    def _classify_http_error(self, exc: requests.HTTPError) -> tuple[str, str]:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code == 403:
            return "source_restricted", "source_blocked"
        if status_code == 429:
            return "error", "rate_limited"
        return "error", f"http_{status_code}" if status_code is not None else "http_error"

    def _to_float(self, value: Any) -> float | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None
