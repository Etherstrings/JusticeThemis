# -*- coding: utf-8 -*-
"""Validation helpers for source URLs and registry-domain matching."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.sources.types import SourceDefinition


def source_allowed_domains(source: SourceDefinition) -> tuple[str, ...]:
    if source.allowed_domains:
        return tuple(_normalize_hostname(domain) for domain in source.allowed_domains if _normalize_hostname(domain))

    derived_domains: list[str] = []
    for entry_url in source.entry_urls:
        hostname = _normalize_hostname(urlsplit(str(entry_url).strip()).hostname or "")
        if hostname and hostname not in derived_domains:
            derived_domains.append(hostname)
    return tuple(derived_domains)


def validate_source_url(url: str, source: SourceDefinition) -> dict[str, object]:
    parts = urlsplit(str(url).strip())
    hostname = _normalize_hostname(parts.hostname or "")
    allowed_domains = source_allowed_domains(source)
    matched_domain = _matched_domain(hostname, allowed_domains)
    is_https = parts.scheme.lower() == "https"
    domain_status = "missing"
    if hostname:
        domain_status = "verified" if matched_domain else "mismatch"
    url_valid = domain_status == "verified" and (is_https or not source.require_https)
    return {
        "hostname": hostname,
        "domain_status": domain_status,
        "matched_domain": matched_domain,
        "allowed_domains": list(allowed_domains),
        "is_https": is_https,
        "https_required": bool(source.require_https),
        "url_valid": url_valid,
    }


def is_source_url_allowed(url: str, source: SourceDefinition) -> bool:
    return bool(validate_source_url(url, source).get("url_valid"))


def _matched_domain(hostname: str, allowed_domains: tuple[str, ...]) -> str | None:
    for domain in allowed_domains:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return domain
    return None


def _normalize_hostname(value: str) -> str:
    candidate = str(value or "").strip().lower().rstrip(".")
    if ":" in candidate:
        candidate = candidate.split(":", 1)[0]
    return candidate
