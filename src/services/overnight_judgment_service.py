# -*- coding: utf-8 -*-
"""Generate one-line overnight judgments with model-optional fallback."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from src.agent.llm_adapter import LLMToolAdapter
from src.overnight.brief_builder import MorningExecutiveBrief

logger = logging.getLogger(__name__)

_FALLBACK_FOCUS = ["自主可控", "高股息", "黄金"]
_FALLBACK_AVOID = ["纯情绪追高", "缺少定价确认的题材"]
_FALLBACK_PRICE_PRESSURE = ["原油", "铜", "进口零部件"]


@dataclass(frozen=True)
class OvernightJudgment:
    """Normalized judgment payload."""

    summary: str
    mode: str


class OvernightJudgmentService:
    """Produce a concise A-share judgment for an overnight event."""

    def __init__(self, adapter: LLMToolAdapter | None = None) -> None:
        self._adapter = adapter or LLMToolAdapter()

    def build_judgment(
        self,
        *,
        brief: MorningExecutiveBrief,
        event: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> OvernightJudgment:
        model_summary = self._build_model_judgment(
            brief=brief,
            event=event,
            evidence_items=evidence_items,
        )
        if model_summary:
            return OvernightJudgment(summary=model_summary, mode="model")

        return OvernightJudgment(
            summary=self._build_heuristic_judgment(
                brief=brief,
                event=event,
                evidence_items=evidence_items,
            ),
            mode="heuristic",
        )

    def _build_model_judgment(
        self,
        *,
        brief: MorningExecutiveBrief,
        event: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> str | None:
        if not self._adapter.is_available:
            return None

        evidence_lines = [
            f"{index}. [{item.get('source_type', 'unknown')}] {item.get('source_name', '未知来源')} | "
            f"{item.get('headline', '')} | {item.get('summary', '')}"
            for index, item in enumerate(evidence_items[:3], start=1)
        ]
        beneficiary_terms = self._flatten_brief_terms(brief.likely_beneficiaries)
        price_terms = self._flatten_brief_terms(brief.what_may_get_more_expensive)

        prompt_lines = [
            "请把下面的隔夜事件翻译成一句给 A 股用户看的盘前判断。",
            "要求：只输出一句中文；不要列表、不要解释过程、不要装作确定；尽量包含先看什么或若不确认就别升级结论。",
            f"核心事实: {str(event.get('core_fact', '')).strip()}",
            f"优先级: {str(event.get('priority_level', '')).strip()}",
            f"置信度: {round(float(event.get('confidence', 0.0) or 0.0) * 100)}%",
            f"摘要: {str(event.get('summary', '')).strip()}",
            f"影响链条: {str(event.get('why_it_matters', '')).strip()}",
            f"可能受益方向: {' / '.join(beneficiary_terms[:4]) or '暂无'}",
            f"可能涨价方向: {' / '.join(price_terms[:4]) or '暂无'}",
            "证据:",
        ]
        prompt_lines.extend(evidence_lines or ["1. 暂无结构化证据卡，只能依赖事件摘要。"])
        user_prompt = "\n".join(prompt_lines)

        try:
            response = self._adapter.call_with_tools(
                messages=[
                    {
                        "role": "system",
                        "content": "You write exactly one Chinese sentence for an A-share pre-market judgment. No markdown, no bullets, no explanation.",
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                tool_declarations={"gemini": [], "openai": [], "anthropic": []},
            )
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("Overnight judgment model call failed: %s", exc)
            return None

        return self._sanitize_sentence(response.content)

    def _build_heuristic_judgment(
        self,
        *,
        brief: MorningExecutiveBrief,
        event: dict[str, Any],
        evidence_items: list[dict[str, Any]],
    ) -> str:
        text = " ".join(
            [
                str(event.get("core_fact", "")).strip().lower(),
                str(event.get("summary", "")).strip().lower(),
                str(event.get("why_it_matters", "")).strip().lower(),
            ]
        )
        confidence = float(event.get("confidence", 0.0) or 0.0)
        official_count = sum(1 for item in evidence_items if item.get("source_type") == "official")
        beneficiary_pool = self._flatten_brief_terms(brief.likely_beneficiaries)
        pressure_pool = self._flatten_brief_terms(brief.what_may_get_more_expensive)

        prefix = "这条暂时只能当辅助证据，" if confidence < 0.7 or official_count == 0 else "这条更像盘前主线预热，"

        if self._has_any_keyword(text, ["tariff", "ustr", "trade", "关税", "贸易", "sanction", "制裁"]):
            focus = " / ".join(
                self._select_terms(
                    beneficiary_pool,
                    ["自主", "军工", "港口", "航运", "替代", "出口"],
                    ["自主可控", "军工电子", "港口航运"],
                )
            )
            return f"{prefix}先看{focus}是否同步加强，若竞价只是一两只独立走强，不要急着把它当全天主线。"

        if self._has_any_keyword(text, ["fed", "cpi", "inflation", "rates", "yield", "通胀", "利率", "pce", "ppi"]):
            focus = " / ".join(
                self._select_terms(
                    beneficiary_pool,
                    ["黄金", "高股息", "资源", "银行"],
                    ["黄金", "高股息", "资源"],
                )
            )
            return f"{prefix}先看{focus}的跷跷板，若美债收益率和人民币方向不共振，只把它当风格切换线。"

        if self._has_any_keyword(text, ["oil", "crude", "gas", "commodity", "原油", "铜", "大宗", "energy", "eia"]):
            price_line = " / ".join(
                self._select_terms(
                    pressure_pool,
                    ["原油", "铜", "燃油", "化工", "运价"],
                    ["原油", "铜", "航空燃油"],
                )
            )
            return f"{prefix}先看{price_line}这条成本传导线，若商品和运价不一起走强，就别把它升级成主线。"

        if self._has_any_keyword(text, ["ai", "gpu", "nvidia", "chip", "semiconductor", "算力", "半导体", "芯片"]):
            focus = " / ".join(
                self._select_terms(
                    beneficiary_pool,
                    ["算力", "半导体", "芯片", "自主", "服务器"],
                    ["算力", "半导体", "自主可控"],
                )
            )
            return f"{prefix}先看{focus}能否形成共振，若只是海外映射但 A 股链条不跟，不要追高。"

        focus = " / ".join(self._select_terms(beneficiary_pool, [], _FALLBACK_FOCUS))
        avoid = " / ".join(self._unique_take(_FALLBACK_AVOID, 2))
        return f"{prefix}先看{focus}有没有同步响应，没有扩散前先回避{avoid}。"

    def _sanitize_sentence(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None

        cleaned = value.strip()
        if not cleaned or cleaned.startswith("All LLM providers failed."):
            return None

        cleaned = re.sub(r"^[>\-\d\.\)\s]+", "", cleaned)
        cleaned = cleaned.replace("\n", " ").strip().strip("\"'“”")
        sentence = re.split(r"[。！？!?]", cleaned, maxsplit=1)[0].strip()
        if not sentence:
            return None
        if len(sentence) > 72:
            sentence = sentence[:72].rstrip("，,;； ")
        if not sentence.endswith("。"):
            sentence = f"{sentence}。"
        return sentence

    def _flatten_brief_terms(self, items: list[dict[str, Any]]) -> list[str]:
        terms: list[str] = []
        for item in items:
            self._collect_terms(item, terms)
        return self._unique_take(terms, 12)

    def _collect_terms(self, value: Any, output: list[str]) -> None:
        if isinstance(value, list):
            for item in value:
                self._collect_terms(item, output)
            return

        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"title", "subtitle", "summary"}:
                    continue
                self._collect_terms(item, output)
            return

        if not isinstance(value, str):
            return

        cleaned = re.sub(r"^[A-Za-z\u4e00-\u9fa5 ]+:\s*", "", value.strip())
        for part in re.split(r"[\/,，、]", cleaned):
            normalized = part.strip()
            if normalized:
                output.append(normalized)

    def _select_terms(
        self,
        pool: list[str],
        keywords: list[str],
        fallback: list[str],
        *,
        limit: int = 3,
    ) -> list[str]:
        if not keywords:
            return self._unique_take(pool or fallback, limit)

        matched = [
            item
            for item in pool
            if self._has_any_keyword(item.lower(), [keyword.lower() for keyword in keywords])
        ]
        if matched:
            return self._unique_take(matched, limit)
        return self._unique_take(fallback, limit)

    def _unique_take(self, values: list[str], limit: int) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
            if len(result) >= limit:
                break
        return result

    def _has_any_keyword(self, text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)
