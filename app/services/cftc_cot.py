# -*- coding: utf-8 -*-
"""CFTC Commitments of Traders signal extraction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

import requests


logger = logging.getLogger(__name__)

CFTC_SODA_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"


def cftc_enabled_from_env() -> bool:
    raw_value = str(os.environ.get("CFTC_ENABLED", "true")).strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class CftcSignalDefinition:
    signal_key: str
    label: str
    commodity_name: str
    bucket: str = ""

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "CftcSignalDefinition":
        signal_key = str(payload.get("signal_key", "")).strip()
        commodity_name = str(payload.get("commodity_name", "")).strip()
        label = str(payload.get("label", "")).strip()
        if not signal_key or not commodity_name:
            raise ValueError("signal_key and commodity_name are required for CFTC signal definitions")
        return cls(
            signal_key=signal_key,
            label=label or signal_key.replace("_", " ").strip() or signal_key,
            commodity_name=commodity_name,
            bucket=str(payload.get("bucket", "")).strip(),
        )


class CFTCCOTSignalService:
    PROVIDER_NAME = "CFTC COT"
    PROVIDER_URL = "https://publicreporting.cftc.gov/"
    ENV_NAME = "CFTC_SIGNAL_CONFIG_JSON"
    DEFAULT_DEFINITIONS = [
        CftcSignalDefinition(signal_key="gold_cot", label="黄金 COT", commodity_name="GOLD", bucket="precious_metals"),
        CftcSignalDefinition(signal_key="silver_cot", label="白银 COT", commodity_name="SILVER", bucket="precious_metals"),
        CftcSignalDefinition(signal_key="crude_oil_cot", label="原油 COT", commodity_name="CRUDE OIL", bucket="energy"),
        CftcSignalDefinition(signal_key="copper_cot", label="铜 COT", commodity_name="COPPER", bucket="industrial_metals"),
    ]

    def __init__(
        self,
        *,
        session: requests.sessions.Session | None = None,
        definitions: list[CftcSignalDefinition] | None = None,
        enabled: bool = True,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.session = session or requests.Session()
        self.definitions = list(definitions or self.DEFAULT_DEFINITIONS)
        self.enabled = bool(enabled)
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    @classmethod
    def from_environment(cls) -> "CFTCCOTSignalService":
        raw_config = str(os.environ.get(cls.ENV_NAME, "")).strip()
        definitions = cls.DEFAULT_DEFINITIONS
        if raw_config:
            parsed = json.loads(raw_config)
            if not isinstance(parsed, list):
                raise ValueError(f"{cls.ENV_NAME} must be a JSON array")
            definitions = [CftcSignalDefinition.from_mapping(dict(item or {})) for item in parsed]
        return cls(definitions=definitions, enabled=cftc_enabled_from_env())

    def collect(
        self,
        *,
        analysis_date: str,
        market_date: str,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        base_payload = {
            "provider_name": self.PROVIDER_NAME,
            "provider_url": self.PROVIDER_URL,
            "analysis_date": str(analysis_date or "").strip(),
            "market_date": str(market_date or "").strip(),
            "generated_at": generated_at,
            "signals": [],
            "signal_count": 0,
            "error_count": 0,
            "errors": [],
        }
        if not self.enabled:
            return {**base_payload, "status": "disabled", "status_reason": "disabled_by_env"}
        previous_nets = self._previous_nets(previous_snapshot)
        signals: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for definition in self.definitions:
            try:
                report = self._latest_report(definition.commodity_name)
                if report is None:
                    raise RuntimeError("no CFTC report found")
                signals.append(self._build_signal(definition=definition, report=report, previous_mm_net=previous_nets.get(definition.signal_key)))
            except Exception as exc:
                logger.warning("Failed to resolve CFTC signal %s: %s", definition.signal_key, exc)
                errors.append({"signal_key": definition.signal_key, "reason": str(exc)})
        return {
            **base_payload,
            "status": "ready" if signals else "error",
            "status_reason": "ok" if signals else "signal_resolution_failed",
            "signals": signals,
            "signal_count": len(signals),
            "error_count": len(errors),
            "errors": errors,
            "headline": self._headline(signals),
        }

    def _latest_report(self, commodity_name: str) -> dict[str, Any] | None:
        escaped_name = commodity_name.upper().replace("'", "''")
        response = self.session.get(
            CFTC_SODA_URL,
            params={
                "$order": "report_date_as_yyyy_mm_dd DESC",
                "$limit": 10,
                "$where": f"commodity_name like '%{escaped_name}%'",
            },
            timeout=self.timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": "overnight-news-handoff/1.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("expected CFTC response to be a list")
        best_record: dict[str, Any] | None = None
        for row in payload:
            if not isinstance(row, dict):
                continue
            if best_record is None or int(row.get("open_interest_all", 0) or 0) > int(best_record.get("open_interest_all", 0) or 0):
                best_record = row
        return best_record

    def _build_signal(
        self,
        *,
        definition: CftcSignalDefinition,
        report: dict[str, Any],
        previous_mm_net: int | None,
    ) -> dict[str, Any]:
        mm_long = self._to_int(report.get("m_money_positions_long_all"))
        mm_short = self._to_int(report.get("m_money_positions_short_all"))
        prod_long = self._to_int(report.get("prod_merc_positions_long_all") or report.get("prod_merc_positions_long"))
        prod_short = self._to_int(report.get("prod_merc_positions_short_all") or report.get("prod_merc_positions_short"))
        open_interest = self._to_int(report.get("open_interest_all"))
        mm_net = mm_long - mm_short
        prod_net = prod_long - prod_short
        mm_net_change = (mm_net - previous_mm_net) if previous_mm_net is not None else None
        bias = "long" if mm_net > 0 else "short" if mm_net < 0 else "flat"
        return {
            "signal_key": definition.signal_key,
            "label": definition.label,
            "bucket": definition.bucket,
            "commodity_name": definition.commodity_name,
            "market_name": str(report.get("market_and_exchange_names", "")).strip(),
            "report_date": str(report.get("report_date_as_yyyy_mm_dd", "")).strip()[:10] or None,
            "managed_money_long": mm_long,
            "managed_money_short": mm_short,
            "managed_money_net": mm_net,
            "managed_money_net_change": mm_net_change,
            "producer_long": prod_long,
            "producer_short": prod_short,
            "producer_net": prod_net,
            "open_interest": open_interest,
            "bias": bias,
            "source_url": self.PROVIDER_URL,
        }

    def _previous_nets(self, snapshot: dict[str, Any] | None) -> dict[str, int]:
        payload = dict(snapshot or {})
        section = dict(payload.get("cftc_signals", {}) or {})
        signals = list(section.get("signals", []) or [])
        previous: dict[str, int] = {}
        for signal in signals:
            if not isinstance(signal, dict):
                continue
            signal_key = str(signal.get("signal_key", "")).strip()
            mm_net = signal.get("managed_money_net")
            if signal_key and isinstance(mm_net, int):
                previous[signal_key] = mm_net
        return previous

    def _headline(self, signals: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for signal in signals[:4]:
            label = str(signal.get("label", "")).strip()
            mm_net = signal.get("managed_money_net")
            bias = str(signal.get("bias", "")).strip()
            if label and isinstance(mm_net, int):
                parts.append(f"{label} {bias} {mm_net:+d}")
        return "；".join(parts)

    def _to_int(self, value: Any) -> int:
        try:
            if value is None or str(value).strip() == "":
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0
