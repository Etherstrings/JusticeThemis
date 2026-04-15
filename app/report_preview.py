# -*- coding: utf-8 -*-
"""CLI for exporting a browser-viewable HTML preview of one daily analysis report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.pipeline import build_runtime_services
from app.services.report_preview import render_daily_report_preview_html


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.report_preview")
    parser.add_argument("--analysis-date", required=True, help="Target analysis date in YYYY-MM-DD.")
    parser.add_argument("--tier", default="premium", choices=("free", "premium"))
    parser.add_argument("--db-path", default="", help="Optional SQLite path override.")
    parser.add_argument("--output-path", default="", help="Optional HTML output path override.")
    parser.add_argument(
        "--source-markdown-path",
        default="",
        help="Optional source markdown artifact path to show inside the preview.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    analysis_date = str(args.analysis_date or "").strip()
    access_tier = str(args.tier or "").strip() or "premium"
    db_path = Path(args.db_path).expanduser() if str(args.db_path or "").strip() else None
    output_path = (
        Path(args.output_path).expanduser()
        if str(args.output_path or "").strip()
        else Path("output") / "previews" / f"daily-{analysis_date}-{access_tier}.html"
    )

    runtime = build_runtime_services(db_path=db_path)
    report = runtime.daily_analysis_service.get_daily_report(
        analysis_date=analysis_date,
        access_tier=access_tier,
    )
    if report is None:
        raise SystemExit(f"Daily analysis report not found for {analysis_date} ({access_tier})")

    html = render_daily_report_preview_html(
        report,
        source_markdown_path=str(args.source_markdown_path or "").strip(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    print(
        json.dumps(
            {
                "analysis_date": analysis_date,
                "access_tier": access_tier,
                "db_path": str(db_path) if db_path is not None else "",
                "output_path": str(output_path),
                "source_markdown_path": str(args.source_markdown_path or "").strip(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
