# -*- coding: utf-8 -*-
"""Canonical product identity and soft-rename compatibility markers."""

from __future__ import annotations

PRODUCT_NAME = "JusticeThemis"
PIPELINE_NAME = "justice_themis"
PACKAGE_NAME = "justice-themis"

LEGACY_PRODUCT_NAME = "overnight-news-handoff"
LEGACY_PIPELINE_COMMAND = "overnight-news-pipeline"
LEGACY_LAUNCHD_COMMAND = "overnight-news-launchd-template"

PIPELINE_COMMAND = "justice-themis-pipeline"
LAUNCHD_COMMAND = "justice-themis-launchd-template"

LAUNCHD_LABEL = "com.etherstrings.justice-themis-pipeline"
LAUNCHD_PLIST_OUTPUT = "output/com.etherstrings.justice-themis-pipeline.plist"
LAUNCHD_INSTALL_PATH = "~/Library/LaunchAgents/com.etherstrings.justice-themis-pipeline.plist"
LAUNCHD_STDOUT_PATH = "/tmp/justice-themis-pipeline.log"
LAUNCHD_STDERR_PATH = "/tmp/justice-themis-pipeline.err.log"

UI_STORAGE_KEY = "justice-themis.admin-access-key"
LEGACY_UI_STORAGE_KEY = "overnight-news-handoff.admin-access-key"
