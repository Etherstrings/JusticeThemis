# -*- coding: utf-8 -*-
"""Deterministic A-share relevance assessment for captured news."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class AShareRelevanceAssessment:
    label: str
    score: int
    reason: str


@dataclass(frozen=True)
class _ThemeDefinition:
    key: str
    patterns: tuple[re.Pattern[str], ...]
    score: int
    reason: str


_SOURCE_BASE_SCORES = {
    "official_data": 3,
    "official_policy": 2,
    "editorial_media": 1,
    "wire_media": 1,
}
_SOURCE_REASON_PREFIX = {
    "official_data": "官方宏观数据源",
    "official_policy": "官方政策源",
    "editorial_media": "媒体快讯源",
    "wire_media": "媒体快讯源",
}
_HIGH_SIGNAL_THEMES: tuple[_ThemeDefinition, ...] = (
    _ThemeDefinition(
        key="trade_supply_chain",
        patterns=(
            re.compile(r"\btrade\b", re.IGNORECASE),
            re.compile(r"\btariff(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bsupply chain\b", re.IGNORECASE),
            re.compile(r"\bsanction(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bexport(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bimport(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bshipping\b", re.IGNORECASE),
            re.compile(r"\bustr\b", re.IGNORECASE),
            re.compile(r"\bsemiconductor(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bchip(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bcritical mineral(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bindustrial\b", re.IGNORECASE),
            re.compile(r"\bmanufactur(?:e|ing)\b", re.IGNORECASE),
        ),
        score=4,
        reason="涉及贸易/关税/供应链",
    ),
    _ThemeDefinition(
        key="macro_rates",
        patterns=(
            re.compile(r"\binflation\b", re.IGNORECASE),
            re.compile(r"\bcpi\b", re.IGNORECASE),
            re.compile(r"\bppi\b", re.IGNORECASE),
            re.compile(r"\bpce\b", re.IGNORECASE),
            re.compile(r"\bgdp\b", re.IGNORECASE),
            re.compile(r"\bretail sales\b", re.IGNORECASE),
            re.compile(r"\bemployment\b", re.IGNORECASE),
            re.compile(r"\bpayroll(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bunemployment\b", re.IGNORECASE),
            re.compile(r"\brate(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bfomc\b", re.IGNORECASE),
            re.compile(r"\btreasury\b", re.IGNORECASE),
        ),
        score=4,
        reason="涉及利率/通胀/宏观数据",
    ),
    _ThemeDefinition(
        key="energy_commodities",
        patterns=(
            re.compile(r"\benergy\b", re.IGNORECASE),
            re.compile(r"\boil\b", re.IGNORECASE),
            re.compile(r"\bcrude\b", re.IGNORECASE),
            re.compile(r"\bnatural gas\b", re.IGNORECASE),
            re.compile(r"\blng\b", re.IGNORECASE),
            re.compile(r"\belectric(?:ity)?\b", re.IGNORECASE),
            re.compile(r"\brefiner(?:y|ies)\b", re.IGNORECASE),
            re.compile(r"\bhormuz\b", re.IGNORECASE),
        ),
        score=3,
        reason="涉及油气/能源价格",
    ),
    _ThemeDefinition(
        key="market_assets",
        patterns=(
            re.compile(r"\bmarket(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bstock(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bshare(?:s)?\b", re.IGNORECASE),
            re.compile(r"\byield(?:s)?\b", re.IGNORECASE),
            re.compile(r"\bfutures\b", re.IGNORECASE),
            re.compile(r"\bdollar\b", re.IGNORECASE),
            re.compile(r"\bprices?\b", re.IGNORECASE),
        ),
        score=2,
        reason="涉及市场风险偏好/资产价格",
    ),
)
_LOW_SIGNAL_THEMES: tuple[_ThemeDefinition, ...] = (
    _ThemeDefinition(
        key="ceremonial_sports",
        patterns=(
            re.compile(r"\bncaa\b", re.IGNORECASE),
            re.compile(r"\bbasketball\b", re.IGNORECASE),
            re.compile(r"\bchampionship\b", re.IGNORECASE),
            re.compile(r"\btournament\b", re.IGNORECASE),
            re.compile(r"\bsports?\b", re.IGNORECASE),
            re.compile(r"\bfootball\b", re.IGNORECASE),
            re.compile(r"\bcoach(?:es)?\b", re.IGNORECASE),
            re.compile(r"\bathlet(?:e|es|ic)\b", re.IGNORECASE),
            re.compile(r"\bcongratulat(?:e|es|ing)\b", re.IGNORECASE),
        ),
        score=-6,
        reason="更偏礼仪/体育消息",
    ),
    _ThemeDefinition(
        key="ceremonial_faith",
        patterns=(
            re.compile(r"\beaster\b", re.IGNORECASE),
            re.compile(r"\bchristian\b", re.IGNORECASE),
            re.compile(r"\bfaith\b", re.IGNORECASE),
            re.compile(r"\bchurch\b", re.IGNORECASE),
            re.compile(r"\bworship\b", re.IGNORECASE),
        ),
        score=-5,
        reason="更偏节庆/宗教表态",
    ),
    _ThemeDefinition(
        key="partisan_politics",
        patterns=(
            re.compile(r"\bradical left\b", re.IGNORECASE),
            re.compile(r"\bwall of shame\b", re.IGNORECASE),
            re.compile(r"\bhealth crisis\b", re.IGNORECASE),
            re.compile(r"\bsmear\b", re.IGNORECASE),
            re.compile(r"\bscandal\b", re.IGNORECASE),
        ),
        score=-5,
        reason="更偏党争/舆论叙事",
    ),
)


def assess_a_share_relevance(
    *,
    source_id: str,
    title: str,
    summary: str,
    coverage_tier: str,
    organization_type: str,
    candidate_url: str = "",
) -> AShareRelevanceAssessment:
    text = " ".join(
        part.strip()
        for part in (title, summary, candidate_url, source_id)
        if part and part.strip()
    )
    source_key = coverage_tier.strip() or organization_type.strip()
    source_prefix = _SOURCE_REASON_PREFIX.get(source_key, "来源待归类")
    score = _SOURCE_BASE_SCORES.get(source_key, 0)

    matched_positive = [theme for theme in _HIGH_SIGNAL_THEMES if _matches_theme(text, theme)]
    matched_negative = [theme for theme in _LOW_SIGNAL_THEMES if _matches_theme(text, theme)]

    score += sum(theme.score for theme in matched_positive)
    score += sum(theme.score for theme in matched_negative)

    if matched_positive and re.search(r"[$%]|\b\d+(?:\.\d+)?\b", text):
        score += 1

    if score >= 6 and matched_positive:
        return AShareRelevanceAssessment(
            label="high",
            score=score,
            reason=f"{source_prefix}；" + "；".join(dict.fromkeys(theme.reason for theme in matched_positive)),
        )

    if matched_negative and not matched_positive:
        return AShareRelevanceAssessment(
            label="low",
            score=score,
            reason=f"{'；'.join(dict.fromkeys(theme.reason for theme in matched_negative))}，对 A 股产业链映射较弱。",
        )

    if score >= 2:
        if matched_positive:
            detail = "；".join(dict.fromkeys(theme.reason for theme in matched_positive))
            return AShareRelevanceAssessment(
                label="medium",
                score=score,
                reason=f"{source_prefix}；{detail}，但还需要结合后续定价链继续判断。",
            )
        return AShareRelevanceAssessment(
            label="medium",
            score=score,
            reason=f"{source_prefix}，但当前标题未体现贸易、利率、能源或产业链主线。",
        )

    return AShareRelevanceAssessment(
        label="low",
        score=score,
        reason="缺少贸易、利率、能源或产业链主线信号，对 A 股映射较弱。",
    )


def _matches_theme(text: str, theme: _ThemeDefinition) -> bool:
    return any(pattern.search(text) for pattern in theme.patterns)
