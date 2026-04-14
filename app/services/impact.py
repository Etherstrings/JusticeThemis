# -*- coding: utf-8 -*-
"""Deterministic impact-outline generation for captured news."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ImpactOutline:
    impact_summary: str
    beneficiary_directions: tuple[str, ...] = ()
    pressured_directions: tuple[str, ...] = ()
    price_up_signals: tuple[str, ...] = ()
    follow_up_checks: tuple[str, ...] = ()


_TRADE_PATTERNS = (
    re.compile(r"\btrade\b", re.IGNORECASE),
    re.compile(r"\bexport(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bimport(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsupply chain\b", re.IGNORECASE),
    re.compile(r"\bustr\b", re.IGNORECASE),
)
_HARD_TRADE_PATTERNS = (
    re.compile(r"\btariff(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bsanction(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bexport control(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bimport restriction(?:s)?\b", re.IGNORECASE),
)
_SEMICONDUCTOR_PATTERNS = (
    re.compile(r"\bsemiconductor(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bchip(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bcritical mineral(?:s)?\b", re.IGNORECASE),
)
_PHARMA_PATTERNS = (
    re.compile(r"\bpharmaceutical\b", re.IGNORECASE),
    re.compile(r"\bdrug(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bmedicine(?:s)?\b", re.IGNORECASE),
)
_ENERGY_PATTERNS = (
    re.compile(r"\boil\b", re.IGNORECASE),
    re.compile(r"\bcrude\b", re.IGNORECASE),
    re.compile(r"\bnatural gas\b", re.IGNORECASE),
    re.compile(r"\blng\b", re.IGNORECASE),
    re.compile(r"\benergy\b", re.IGNORECASE),
    re.compile(r"\bhormuz\b", re.IGNORECASE),
)
_HAWKISH_MACRO_PATTERNS = (
    re.compile(r"\binflation\b", re.IGNORECASE),
    re.compile(r"\bcpi\b", re.IGNORECASE),
    re.compile(r"\bppi\b", re.IGNORECASE),
    re.compile(r"\bpce\b", re.IGNORECASE),
    re.compile(r"\brate(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bfomc\b", re.IGNORECASE),
    re.compile(r"\byield(?:s)?\b", re.IGNORECASE),
)
_DOVISH_MACRO_PATTERNS = (
    re.compile(r"\brate cut(?:s)?\b", re.IGNORECASE),
    re.compile(r"\bdisinflation\b", re.IGNORECASE),
    re.compile(r"\bcooling inflation\b", re.IGNORECASE),
    re.compile(r"\bslowing inflation\b", re.IGNORECASE),
    re.compile(r"\bsoft landing\b", re.IGNORECASE),
)


def build_impact_outline(
    *,
    source_id: str,
    title: str,
    summary: str,
    relevance_label: str,
) -> ImpactOutline:
    text = " ".join(part.strip() for part in (title, summary, source_id) if part and part.strip())

    beneficiaries: list[str] = []
    pressured: list[str] = []
    price_up: list[str] = []
    follow_up: list[str] = []
    summary_parts: list[str] = []

    has_trade = _matches_any(text, _TRADE_PATTERNS)
    has_hard_trade = _matches_any(text, _HARD_TRADE_PATTERNS)
    has_semiconductor = _matches_any(text, _SEMICONDUCTOR_PATTERNS)
    has_pharma = _matches_any(text, _PHARMA_PATTERNS)
    has_energy = _matches_any(text, _ENERGY_PATTERNS)
    has_hawkish_macro = _matches_any(text, _HAWKISH_MACRO_PATTERNS)
    has_dovish_macro = _matches_any(text, _DOVISH_MACRO_PATTERNS)

    if has_trade:
        if source_id == "census_economic_indicators":
            summary_parts.append("这是外需与贸易景气验证")
            beneficiaries.extend(
                [
                    "出口链景气跟踪",
                    "航运港口景气跟踪",
                ]
            )
            follow_up.extend(
                [
                    "确认进口、出口和库存分项是否延续同方向变化。",
                    "结合美元、运价和后续月度数据验证传导强度。",
                ]
            )
        else:
            summary_parts.append("消息主线落在贸易/关税/供应链")
            beneficiaries.append("进口替代制造链")
            if has_semiconductor:
                beneficiaries.extend(
                    [
                        "自主可控半导体链",
                        "国产替代设备材料",
                    ]
                )
                price_up.append("进口芯片/关键零部件")
            if has_pharma:
                beneficiaries.append("创新药/CXO")
            if has_hard_trade:
                pressured.extend(
                    [
                        "对美出口链",
                        "依赖进口零部件的装配链",
                    ]
                )
                follow_up.append("确认税率、覆盖商品清单和生效日期。")
            else:
                follow_up.append("确认协议条款、适用范围和执行时间。")
            follow_up.append("确认是否配套豁免、补贴或本土采购政策。")

    if has_energy:
        summary_parts.append("油气与航运扰动可能向成本线传导")
        beneficiaries.extend(
            [
                "油气开采",
                "油服",
            ]
        )
        pressured.extend(
            [
                "航空与燃油敏感运输链",
                "化工下游成本敏感链",
            ]
        )
        price_up.extend(
            [
                "原油/燃料油",
                "天然气/LNG",
            ]
        )
        follow_up.append("确认航运通道恢复时间、库存变化和油价冲击持续性。")

    if has_hawkish_macro and not has_dovish_macro:
        summary_parts.append("偏紧的利率/通胀信号可能先影响估值切换")
        beneficiaries.extend(
            [
                "银行/保险",
                "高股息防御",
            ]
        )
        pressured.append("高估值成长链")
        follow_up.append("确认后续 FOMC 路径和下一次通胀/就业数据。")

    if has_dovish_macro and not has_hawkish_macro:
        summary_parts.append("偏松的利率信号更利于利率敏感资产")
        beneficiaries.append("成长科技/创新药等利率敏感方向")
        follow_up.append("确认降息节奏是否被后续数据验证。")

    if relevance_label == "low":
        return ImpactOutline(
            impact_summary="当前更像噪音或泛政治消息，不建议直接映射板块。",
            follow_up_checks=("等待更明确的产业、价格或政策细则。",),
        )

    if not summary_parts:
        return ImpactOutline(
            impact_summary="当前只确认这是需要跟踪的消息，尚不足以直接下受益或涨价结论。",
            follow_up_checks=(
                "确认是否涉及关税、制裁、补贴、采购或价格机制。",
                "确认执行日期、行业清单和影响范围细则。",
            ),
        )

    impact_summary = "；".join(summary_parts) + "。"
    if relevance_label != "high":
        follow_up.append("当前仍需等待更具体的正式文件或数据来验证映射方向。")

    return ImpactOutline(
        impact_summary=impact_summary,
        beneficiary_directions=_dedupe(beneficiaries),
        pressured_directions=_dedupe(pressured),
        price_up_signals=_dedupe(price_up),
        follow_up_checks=_dedupe(follow_up),
    )


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)
