# -*- coding: utf-8 -*-
"""Render launchd plist templates and local operation plans."""

from __future__ import annotations

from html import escape
import json


def build_launchd_operation_plan(
    *,
    label: str,
    generated_plist_path: str,
    install_path: str,
    stdout_path: str,
    stderr_path: str,
) -> dict[str, str]:
    normalized_label = str(label).strip()
    normalized_generated_plist_path = str(generated_plist_path).strip()
    normalized_install_path = str(install_path).strip()
    normalized_stdout = str(stdout_path).strip()
    normalized_stderr = str(stderr_path).strip()
    domain_target = f"gui/$(id -u)/{normalized_label}"
    domain_bootstrap = f"gui/$(id -u) {normalized_install_path}"
    return {
        "label": normalized_label,
        "generated_plist_path": normalized_generated_plist_path,
        "install_path": normalized_install_path,
        "copy_command": f"cp {normalized_generated_plist_path} {normalized_install_path}",
        "load_command": f"launchctl bootstrap {domain_bootstrap}",
        "unload_command": f"launchctl bootout {domain_bootstrap}",
        "reload_command": (
            f"launchctl bootout {domain_bootstrap} || true\n"
            f"launchctl bootstrap {domain_bootstrap}"
        ),
        "status_command": f"launchctl print {domain_target}",
        "tail_stdout_command": f"tail -f {normalized_stdout}",
        "tail_stderr_command": f"tail -f {normalized_stderr}",
    }


def render_launchd_setup_markdown(plan: dict[str, str]) -> str:
    lines = [
        "# launchd Setup",
        "",
        f"- Label: {str(plan.get('label', '')).strip()}",
        f"- Generated Plist: {str(plan.get('generated_plist_path', '')).strip()}",
        f"- Install Path: {str(plan.get('install_path', '')).strip()}",
        "",
        "## Install",
        "",
        "```bash",
        str(plan.get("copy_command", "")).strip(),
        str(plan.get("load_command", "")).strip(),
        "```",
        "",
        "## Reload",
        "",
        "```bash",
        str(plan.get("reload_command", "")).strip(),
        "```",
        "",
        "## Unload",
        "",
        "```bash",
        str(plan.get("unload_command", "")).strip(),
        "```",
        "",
        "## Inspect",
        "",
        "```bash",
        str(plan.get("status_command", "")).strip(),
        str(plan.get("tail_stdout_command", "")).strip(),
        str(plan.get("tail_stderr_command", "")).strip(),
        "```",
        "",
    ]
    return "\n".join(lines)


def render_launchd_operation_plan_json(plan: dict[str, str]) -> str:
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def render_launchd_plist(
    *,
    label: str,
    working_directory: str,
    shell_command: str,
    stdout_path: str,
    stderr_path: str,
    hour: int = 6,
    minute: int = 15,
) -> str:
    escaped_label = escape(str(label).strip())
    escaped_workdir = escape(str(working_directory).strip())
    escaped_command = escape(str(shell_command).strip())
    escaped_stdout = escape(str(stdout_path).strip())
    escaped_stderr = escape(str(stderr_path).strip())

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{escaped_label}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/bin/zsh</string>\n"
        "    <string>-lc</string>\n"
        f"    <string>{escaped_command}</string>\n"
        "  </array>\n"
        "  <key>WorkingDirectory</key>\n"
        f"  <string>{escaped_workdir}</string>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n"
        "    <key>Hour</key>\n"
        f"    <integer>{max(0, min(23, int(hour)))}</integer>\n"
        "    <key>Minute</key>\n"
        f"    <integer>{max(0, min(59, int(minute)))}</integer>\n"
        "  </dict>\n"
        "  <key>StandardOutPath</key>\n"
        f"  <string>{escaped_stdout}</string>\n"
        "  <key>StandardErrorPath</key>\n"
        f"  <string>{escaped_stderr}</string>\n"
        "  <key>RunAtLoad</key>\n"
        "  <false/>\n"
        "</dict>\n"
        "</plist>\n"
    )
