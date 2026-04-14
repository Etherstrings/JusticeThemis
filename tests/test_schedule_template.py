# -*- coding: utf-8 -*-
"""Tests for launchd schedule template rendering."""

from __future__ import annotations

import json

from app.schedule_template import main
from app.services.launchd_template import (
    build_launchd_operation_plan,
    render_launchd_plist,
    render_launchd_setup_markdown,
)


def test_render_launchd_plist_includes_label_command_and_schedule() -> None:
    plist = render_launchd_plist(
        label="com.etherstrings.overnight-news-pipeline",
        working_directory="/Users/example/overnight-news-handoff",
        shell_command="uv run python -m app.pipeline --analysis-date $(date +%F)",
        stdout_path="/tmp/overnight-news-pipeline.log",
        stderr_path="/tmp/overnight-news-pipeline.err.log",
        hour=6,
        minute=15,
    )

    assert "<string>com.etherstrings.overnight-news-pipeline</string>" in plist
    assert "<string>/bin/zsh</string>" in plist
    assert "uv run python -m app.pipeline --analysis-date $(date +%F)" in plist
    assert "<key>WorkingDirectory</key>" in plist
    assert "<string>/Users/example/overnight-news-handoff</string>" in plist
    assert "<integer>6</integer>" in plist
    assert "<integer>15</integer>" in plist


def test_build_launchd_operation_plan_includes_install_load_and_status_commands() -> None:
    plan = build_launchd_operation_plan(
        label="com.etherstrings.overnight-news-pipeline",
        generated_plist_path="/Users/example/overnight-news-handoff/output/job.plist",
        install_path="~/Library/LaunchAgents/com.etherstrings.overnight-news-pipeline.plist",
        stdout_path="/tmp/overnight-news-pipeline.log",
        stderr_path="/tmp/overnight-news-pipeline.err.log",
    )

    assert plan["install_path"] == "~/Library/LaunchAgents/com.etherstrings.overnight-news-pipeline.plist"
    assert plan["copy_command"].startswith("cp ")
    assert "launchctl bootstrap gui/$(id -u)" in plan["load_command"]
    assert "launchctl bootout gui/$(id -u)" in plan["unload_command"]
    assert "launchctl print gui/$(id -u)/com.etherstrings.overnight-news-pipeline" in plan["status_command"]
    assert "/tmp/overnight-news-pipeline.log" in plan["tail_stdout_command"]
    assert "/tmp/overnight-news-pipeline.err.log" in plan["tail_stderr_command"]


def test_render_launchd_setup_markdown_lists_operational_steps() -> None:
    markdown = render_launchd_setup_markdown(
        {
            "label": "com.etherstrings.overnight-news-pipeline",
            "generated_plist_path": "/Users/example/overnight-news-handoff/output/job.plist",
            "install_path": "~/Library/LaunchAgents/com.etherstrings.overnight-news-pipeline.plist",
            "copy_command": "cp a b",
            "load_command": "launchctl bootstrap gui/$(id -u) b",
            "unload_command": "launchctl bootout gui/$(id -u) b",
            "reload_command": "launchctl bootout gui/$(id -u) b && launchctl bootstrap gui/$(id -u) b",
            "status_command": "launchctl print gui/$(id -u)/com.etherstrings.overnight-news-pipeline",
            "tail_stdout_command": "tail -f /tmp/stdout.log",
            "tail_stderr_command": "tail -f /tmp/stderr.log",
        }
    )

    assert "# launchd Setup" in markdown
    assert "launchctl bootstrap gui/$(id -u) b" in markdown
    assert "launchctl bootout gui/$(id -u) b" in markdown
    assert "tail -f /tmp/stdout.log" in markdown


def test_schedule_template_cli_can_write_plan_json_and_markdown(tmp_path) -> None:
    output_plist = tmp_path / "job.plist"
    plan_json = tmp_path / "launchd-plan.json"
    plan_markdown = tmp_path / "launchd-plan.md"

    exit_code = main(
        [
            "--working-directory",
            "/Users/example/overnight-news-handoff",
            "--output-path",
            str(output_plist),
            "--plan-json-path",
            str(plan_json),
            "--plan-markdown-path",
            str(plan_markdown),
        ]
    )

    assert exit_code == 0
    assert output_plist.exists()
    assert plan_json.exists()
    assert plan_markdown.exists()
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    assert plan["label"] == "com.etherstrings.justice-themis-pipeline"
    assert plan["install_path"] == "~/Library/LaunchAgents/com.etherstrings.justice-themis-pipeline.plist"
    assert "load_command" in plan
    assert "install_path" in plan
    assert "launchctl bootstrap gui/$(id -u)" in plan["load_command"]
    assert plan["tail_stdout_command"] == "tail -f /tmp/justice-themis-pipeline.log"
    assert plan["tail_stderr_command"] == "tail -f /tmp/justice-themis-pipeline.err.log"
