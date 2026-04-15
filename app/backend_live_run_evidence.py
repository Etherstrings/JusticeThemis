# -*- coding: utf-8 -*-
"""CLI entrypoint for the Readhub backend live run evidence workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.pipeline import build_runtime_services
from app.services.backend_live_run_evidence import BackendLiveRunEvidenceService
from app.sources.registry import build_default_source_registry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backend_live_run_evidence")
    parser.add_argument("--analysis-date", required=True, help="Target analysis date in YYYY-MM-DD.")
    parser.add_argument("--db-path", default="", help="Optional isolated SQLite path.")
    parser.add_argument("--output-dir", default="", help="Optional output directory override.")
    parser.add_argument("--limit-per-source", type=int, default=2)
    parser.add_argument("--max-sources", type=int, default=0)
    parser.add_argument("--recent-limit", type=int, default=20)
    parser.add_argument("--skip-market-snapshot", action="store_true")
    parser.add_argument("--skip-daily-analysis", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    analysis_date = str(args.analysis_date or "").strip()
    output_dir = Path(args.output_dir or f"output/live-runs/readhub-{analysis_date}")
    db_path = Path(args.db_path or f"data/live-runs/readhub-{analysis_date}.db")
    runtime = build_runtime_services(db_path=db_path)
    service = BackendLiveRunEvidenceService(
        capture_service=runtime.capture_service,
        market_snapshot_service=runtime.market_snapshot_service,
        daily_analysis_service=runtime.daily_analysis_service,
    )
    result = service.run(
        analysis_date=analysis_date,
        output_dir=output_dir,
        db_path=db_path,
        limit_per_source=max(1, int(args.limit_per_source)),
        max_sources=max(1, int(args.max_sources or len(build_default_source_registry()))),
        recent_limit=max(1, int(args.recent_limit)),
        include_market_snapshot=not bool(args.skip_market_snapshot),
        include_daily_analysis=not bool(args.skip_daily_analysis),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
