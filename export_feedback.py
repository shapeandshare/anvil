#!/usr/bin/env python3
"""Export all feedback reports from a running anvil instance via the API.

Usage:
    python export_feedback.py [--host http://localhost:8080] [--api-key KEY]

Output: Writes feedback-export.json with all reports and their annotations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request


def _req(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url)
    req.add_header("X-API-Key", api_key)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    parser = argparse.ArgumentParser(description="Export feedback reports from anvil API")
    parser.add_argument("--host", default="http://localhost:8080", help="Base URL of running anvil instance")
    parser.add_argument("--api-key", default=None, help="API key (required, or set ANVIL_API_KEY env var)")
    parser.add_argument("--output", default="feedback-export.json", help="Output JSON file")
    args = parser.parse_args()
    api_key = args.api_key or os.environ.get("ANVIL_API_KEY")
    if not api_key:
        parser.error("--api-key is required (or set ANVIL_API_KEY env var)")

    base = args.host.rstrip("/")

    print(f"Fetching feedback reports from {base}/v1/feedback ...", file=sys.stderr)
    data = _req(f"{base}/v1/feedback", api_key)
    reports = data.get("reports", [])
    total = data.get("total", len(reports))
    print(f"Found {total} report(s)", file=sys.stderr)

    if not reports:
        print("No feedback reports to export.", file=sys.stderr)
        sys.exit(0)

    # Step 2: Export each report with full details (annotations, etc.)
    exports = []
    for r in reports:
        rid = r["id"]
        print(f"  Exporting report #{rid} ...", file=sys.stderr)
        export_data = _req(f"{base}/v1/feedback/{rid}/export", api_key)
        report = export_data.get("export", {})
        exports.append(report)
        time.sleep(0.1)

    # Step 3: Write output
    output = {
        "total": len(exports),
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "reports": exports,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nDone. Wrote {len(exports)} report(s) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()