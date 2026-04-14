# -*- coding: utf-8 -*-
"""Tests for legacy remote entrypoint compatibility shims."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from fastapi import FastAPI

from app.product_identity import PRODUCT_NAME


REPO_ROOT = Path(__file__).resolve().parent.parent


def _import_fresh(module_name: str):
    sys.modules.pop(module_name, None)
    module_path = REPO_ROOT / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_legacy_entrypoint_modules_expose_justice_themis_app(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OVERNIGHT_NEWS_DB_PATH", str(tmp_path / "legacy-entrypoints.db"))

    for module_name in ("main", "server", "webui"):
        module = _import_fresh(module_name)

        assert isinstance(module.app, FastAPI)
        assert module.app.title == PRODUCT_NAME
        assert callable(module.main)
