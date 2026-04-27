# -*- coding: utf-8 -*-
"""CLI entrypoint for offline result-first artifact inspection and re-export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app.services.artifact_inspection import (
    inspect_local_data_availability,
    inspect_result_first_artifact_freshness,
    reexport_result_first_artifacts_from_db,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.artifact_inspection")
    parser.add_argument("--output-dir", default="", help="Target live-run output directory.")
    parser.add_argument("--db-path", default="", help="Optional database path for local data availability inspection.")
    parser.add_argument("--analysis-date", default="", help="Analysis date used by DB re-export mode.")
    parser.add_argument("--reexport-from-db", action="store_true", help="Re-export group/desk result-first artifacts from an existing DB.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    output_dir = str(args.output_dir).strip()
    db_path = str(args.db_path).strip()
    analysis_date = str(args.analysis_date).strip()
    if args.reexport_from_db:
        if not db_path or not output_dir:
            parser.error("--reexport-from-db requires both --db-path and --output-dir")
        result = reexport_result_first_artifacts_from_db(
            db_path=Path(db_path),
            output_dir=Path(output_dir),
            analysis_date=analysis_date,
        )
    elif db_path:
        result = inspect_local_data_availability(Path(db_path))
    elif output_dir:
        result = inspect_result_first_artifact_freshness(Path(output_dir))
    else:
        parser.error("one of --output-dir or --db-path is required")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
