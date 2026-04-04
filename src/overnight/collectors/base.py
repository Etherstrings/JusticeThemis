# -*- coding: utf-8 -*-
"""Collector protocol contract for overnight sources."""

from __future__ import annotations

from typing import Protocol

from src.overnight.types import SourceCandidate, SourceDefinition


class BaseCollector(Protocol):
    def collect(self, source: SourceDefinition) -> list[SourceCandidate]:
        ...
