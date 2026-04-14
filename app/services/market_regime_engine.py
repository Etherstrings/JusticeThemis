# -*- coding: utf-8 -*-
"""Deterministic regime grounding from normalized market observations."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any


@dataclass(frozen=True)
class MarketRegimeRule:
    regime_key: str
    direction: str
    required_signals: tuple[tuple[str, str], ...]
    supporting_signals: tuple[tuple[str, str], ...] = ()
    disqualifying_signals: tuple[tuple[str, str], ...] = ()
    minimum_completeness_ratio: float = 0.67
    minimum_strength_score: float = 1.0
    conflict_policy: str = "downgrade"
    freshness_policy: str = "strict"


_DEFAULT_RULES: tuple[MarketRegimeRule, ...] = (
    MarketRegimeRule(
        regime_key="technology_risk_on",
        direction="bullish",
        required_signals=(("SOXX", "up"), ("XLK", "up"), ("^IXIC", "up")),
        supporting_signals=(("^VIX", "down"), ("^TNX", "down")),
        disqualifying_signals=(("^VIX", "up"), ("^TNX", "up")),
        minimum_completeness_ratio=2 / 3,
        minimum_strength_score=1.0,
    ),
    MarketRegimeRule(
        regime_key="rates_pressure",
        direction="bearish",
        required_signals=(("^TNX", "up"), ("DX-Y.NYB", "up"), ("CNH=X", "up")),
        supporting_signals=(("^IXIC", "down"), ("XLK", "down")),
        disqualifying_signals=(("^TNX", "down"), ("DX-Y.NYB", "down")),
        minimum_completeness_ratio=2 / 3,
        minimum_strength_score=0.6,
    ),
    MarketRegimeRule(
        regime_key="safe_haven_flow",
        direction="bullish",
        required_signals=(("GC=F", "up"), ("SI=F", "up"), ("^VIX", "up")),
        supporting_signals=(("^GSPC", "down"), ("^IXIC", "down")),
        disqualifying_signals=(("^GSPC", "up"), ("^IXIC", "up")),
        minimum_completeness_ratio=2 / 3,
        minimum_strength_score=0.8,
    ),
    MarketRegimeRule(
        regime_key="energy_inflation_impulse",
        direction="bullish",
        required_signals=(("CL=F", "up"), ("BZ=F", "up"), ("NG=F", "up")),
        supporting_signals=(("XLE", "up"),),
        disqualifying_signals=(("CL=F", "down"), ("BZ=F", "down")),
        minimum_completeness_ratio=2 / 3,
        minimum_strength_score=1.0,
    ),
    MarketRegimeRule(
        regime_key="usd_strengthening",
        direction="bullish",
        required_signals=(("DX-Y.NYB", "up"), ("CNH=X", "up")),
        supporting_signals=(("^TNX", "up"),),
        disqualifying_signals=(("DX-Y.NYB", "down"), ("CNH=X", "down")),
        minimum_completeness_ratio=1.0,
        minimum_strength_score=0.5,
    ),
    MarketRegimeRule(
        regime_key="china_proxy_strength",
        direction="bullish",
        required_signals=(("KWEB", "up"), ("FXI", "up")),
        supporting_signals=(("CNH=X", "down"),),
        disqualifying_signals=(("KWEB", "down"), ("FXI", "down")),
        minimum_completeness_ratio=0.5,
        minimum_strength_score=0.8,
    ),
)


class MarketRegimeEngine:
    def __init__(self, *, rules: tuple[MarketRegimeRule, ...] | None = None) -> None:
        self.rules = tuple(rules or _DEFAULT_RULES)

    def evaluate(
        self,
        *,
        analysis_date: str,
        observations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbol_map = self._observation_symbol_map(observations)
        evaluations = [
            self._evaluate_rule(
                analysis_date=analysis_date,
                rule=rule,
                symbol_map=symbol_map,
            )
            for rule in self.rules
        ]
        market_regimes = sorted(
            [item for item in evaluations if item["triggered"]],
            key=lambda item: (
                float(item.get("strength", 0.0) or 0.0),
                str(item.get("regime_key", "")),
            ),
            reverse=True,
        )
        return {
            "market_regimes": market_regimes,
            "market_regime_evaluations": evaluations,
        }

    def _evaluate_rule(
        self,
        *,
        analysis_date: str,
        rule: MarketRegimeRule,
        symbol_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        required_count = len(rule.required_signals)
        present_required = 0
        matched_required = 0
        strength_components: list[float] = []
        supporting_observations: list[dict[str, Any]] = []
        driving_symbols: list[str] = []
        suppressed_by: list[str] = []
        evaluation_notes: list[str] = []

        for symbol, expected_direction in rule.required_signals:
            observation = symbol_map.get(symbol)
            if observation is None:
                continue
            if str(observation.get("freshness_status", "")).strip() != "fresh":
                suppressed_by.append("stale_market_inputs")
                continue
            present_required += 1
            signed_change = _signed_change_pct(observation, expected_direction)
            if signed_change > 0:
                matched_required += 1
                strength_components.append(min(signed_change, 5.0))
                driving_symbols.append(symbol)
                supporting_observations.append(
                    self._supporting_observation_payload(
                        observation=observation,
                        expected_direction=expected_direction,
                        role="required",
                    )
                )

        completeness_ratio = round(present_required / required_count, 4) if required_count else 1.0
        minimum_match_count = max(1, ceil(required_count * rule.minimum_completeness_ratio)) if required_count else 0
        if present_required < minimum_match_count:
            suppressed_by.append("missing_required_observations")

        for symbol, expected_direction in rule.supporting_signals:
            observation = symbol_map.get(symbol)
            if observation is None or str(observation.get("freshness_status", "")).strip() != "fresh":
                continue
            signed_change = _signed_change_pct(observation, expected_direction)
            if signed_change > 0:
                strength_components.append(min(signed_change * 0.5, 2.0))
                supporting_observations.append(
                    self._supporting_observation_payload(
                        observation=observation,
                        expected_direction=expected_direction,
                        role="supporting",
                    )
                )

        conflict_hits = 0
        for symbol, expected_direction in rule.disqualifying_signals:
            observation = symbol_map.get(symbol)
            if observation is None or str(observation.get("freshness_status", "")).strip() != "fresh":
                continue
            signed_change = _signed_change_pct(observation, expected_direction)
            if signed_change > 0:
                conflict_hits += 1
                evaluation_notes.append(
                    f"{symbol} moved {str(expected_direction).strip()} against {rule.regime_key}"
                )

        strength = round(sum(strength_components) / max(1, required_count), 4)
        triggered = (
            present_required >= minimum_match_count
            and matched_required >= minimum_match_count
            and strength >= rule.minimum_strength_score
        )
        if not triggered and strength < rule.minimum_strength_score:
            suppressed_by.append("insufficient_market_strength")

        confidence = "low"
        if triggered:
            confidence = "high" if completeness_ratio >= 1.0 and conflict_hits == 0 else "medium"
            if conflict_hits > 0:
                suppressed_by.append("conflicting_observations")

        regime_id = f"{analysis_date}__{rule.regime_key}"
        return {
            "regime_id": regime_id,
            "regime_key": rule.regime_key,
            "triggered": triggered,
            "direction": rule.direction if triggered else "neutral",
            "strength": strength,
            "confidence": confidence,
            "completeness_ratio": completeness_ratio,
            "driving_symbols": driving_symbols,
            "supporting_observations": supporting_observations,
            "suppressed_by": list(dict.fromkeys(suppressed_by)),
            "evaluation_notes": evaluation_notes,
        }

    def _observation_symbol_map(self, observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        symbol_map: dict[str, dict[str, Any]] = {}
        for item in observations:
            symbol = str(item.get("symbol", "")).strip()
            if not symbol:
                continue
            current = symbol_map.get(symbol)
            if current is None or bool(item.get("is_primary")):
                symbol_map[symbol] = dict(item)
        return symbol_map

    def _supporting_observation_payload(
        self,
        *,
        observation: dict[str, Any],
        expected_direction: str,
        role: str,
    ) -> dict[str, Any]:
        return {
            "symbol": str(observation.get("symbol", "")).strip(),
            "bucket": str(observation.get("bucket", "")).strip(),
            "change_pct": float(observation.get("change_pct", 0.0) or 0.0),
            "expected_direction": expected_direction,
            "role": role,
        }


def _signed_change_pct(observation: dict[str, Any], expected_direction: str) -> float:
    try:
        numeric = float(observation.get("change_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return numeric if expected_direction == "up" else -numeric
