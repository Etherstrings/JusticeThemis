# -*- coding: utf-8 -*-
"""CLI to generate a launchd plist template for the overnight pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from app.product_identity import (
    LAUNCHD_INSTALL_PATH,
    LAUNCHD_LABEL,
    LAUNCHD_PLIST_OUTPUT,
    LAUNCHD_STDERR_PATH,
    LAUNCHD_STDOUT_PATH,
)
from app.services.launchd_template import (
    build_launchd_operation_plan,
    render_launchd_operation_plan_json,
    render_launchd_plist,
    render_launchd_setup_markdown,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a launchd plist template for the JusticeThemis pipeline.")
    parser.add_argument("--label", default=LAUNCHD_LABEL)
    parser.add_argument("--working-directory", default=str(Path.cwd()))
    parser.add_argument("--output-path", default=LAUNCHD_PLIST_OUTPUT)
    parser.add_argument("--install-path", default=LAUNCHD_INSTALL_PATH)
    parser.add_argument("--plan-json-path", default="")
    parser.add_argument("--plan-markdown-path", default="")
    parser.add_argument("--stdout-path", default=LAUNCHD_STDOUT_PATH)
    parser.add_argument("--stderr-path", default=LAUNCHD_STDERR_PATH)
    parser.add_argument("--hour", type=int, default=6)
    parser.add_argument("--minute", type=int, default=15)
    parser.add_argument(
        "--shell-command",
        default=(
            "cd {working_directory} && "
            "env UV_CACHE_DIR=/tmp/uv-cache uv run python -m app.pipeline "
            "--max-sources 16 --limit-per-source 4 --recent-limit 40 "
            "--output-path output/pipeline-summary-$(date +%F).json "
            "--summary-markdown-path output/pipeline-summary-$(date +%F).md "
            "--fail-on-health-status fail"
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    working_directory = str(Path(args.working_directory).expanduser())
    shell_command = str(args.shell_command).format(working_directory=working_directory)
    plist = render_launchd_plist(
        label=args.label,
        working_directory=working_directory,
        shell_command=shell_command,
        stdout_path=args.stdout_path,
        stderr_path=args.stderr_path,
        hour=args.hour,
        minute=args.minute,
    )

    output_path = Path(args.output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(plist, encoding="utf-8")
    operation_plan = build_launchd_operation_plan(
        label=args.label,
        generated_plist_path=str(output_path),
        install_path=str(args.install_path),
        stdout_path=str(args.stdout_path),
        stderr_path=str(args.stderr_path),
    )

    if args.plan_json_path:
        plan_json_path = Path(args.plan_json_path).expanduser()
        plan_json_path.parent.mkdir(parents=True, exist_ok=True)
        plan_json_path.write_text(render_launchd_operation_plan_json(operation_plan), encoding="utf-8")

    if args.plan_markdown_path:
        plan_markdown_path = Path(args.plan_markdown_path).expanduser()
        plan_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        plan_markdown_path.write_text(render_launchd_setup_markdown(operation_plan), encoding="utf-8")

    print(output_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
