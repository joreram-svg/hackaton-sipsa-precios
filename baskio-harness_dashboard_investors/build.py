#!/usr/bin/env python
"""Baskio dashboard build harness — one shot.

Pipeline: fetch (Supabase) -> compute (metrics/insights/forecast)
          -> render (inject into template) -> validate (quality gate)
          -> promote (only if it passed) -> changelog.

A failed build NEVER overwrites the last known-good dashboard: it is written
to output/history/rejected_<ts>.html for inspection instead, and the failure
reasons go into CHANGELOG.md so the next run (human or scheduled) can see
what needs fixing.

Usage:
    python build.py                # fetch fresh data from Supabase and build
    python build.py --dry-run      # build + validate, never promote
    python build.py --dsn "..."    # override BASKIO_DSN env var
"""
import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR / "src"))

from fetch_data import fetch_dataset  # noqa: E402
from compute import build_full_dataset  # noqa: E402
from render import render_html  # noqa: E402
from validate import validate_dataset, validate_html  # noqa: E402
from changelog import diff_summary, write_entry, load_prev_dataset  # noqa: E402

TEMPLATE_PATH = HARNESS_DIR / "template.html"
OUTPUT_DIR = HARNESS_DIR / "output"
HISTORY_DIR = OUTPUT_DIR / "history"
CURRENT_HTML = OUTPUT_DIR / "baskio_dashboard.html"
CURRENT_DATASET = OUTPUT_DIR / "latest_dataset.json"
CHANGELOG_PATH = HARNESS_DIR / "CHANGELOG.md"
LOG_PATH = HARNESS_DIR / "harness.log"


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # Some Windows consoles (cp1252) can't print arrows/emoji — degrade gracefully.
        print(line.encode(sys.stdout.encoding or "ascii", errors="replace").decode(sys.stdout.encoding or "ascii"))
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_once(dsn: str | None, dry_run: bool) -> bool:
    """Returns True if a new dashboard was promoted."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    try:
        log("Fetching dataset from Supabase...")
        raw = fetch_dataset(dsn)
        log(f"Fetched {raw['meta']['n_products']} products, "
            f"coverage {raw['meta']['start_date']} -> {raw['meta']['max_date']}.")

        log("Computing metrics, insights and forecasts...")
        dataset = build_full_dataset(raw)

        data_issues = validate_dataset(dataset)
        if data_issues:
            log(f"REJECTED at data validation: {len(data_issues)} issue(s).")
            write_entry(CHANGELOG_PATH, [], status="RECHAZADO (validación de datos)", issues=data_issues)
            (HISTORY_DIR / f"rejected_{ts}_dataset.json").write_text(
                json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return False

        log("Rendering HTML...")
        html = render_html(TEMPLATE_PATH, dataset)

        html_issues = validate_html(html)
        if html_issues:
            log(f"REJECTED at HTML validation: {len(html_issues)} issue(s).")
            write_entry(CHANGELOG_PATH, [], status="RECHAZADO (validación de HTML)", issues=html_issues)
            (HISTORY_DIR / f"rejected_{ts}.html").write_text(html, encoding="utf-8")
            return False

        prev_dataset = load_prev_dataset(CURRENT_DATASET)
        summary = diff_summary(prev_dataset, dataset)

        if dry_run:
            log("Dry run OK — build passed validation but was not promoted.")
            write_entry(CHANGELOG_PATH, summary, status="DRY-RUN (no promovido)")
            return False

        # Promote: archive current, write new current, snapshot dataset, changelog.
        if CURRENT_HTML.exists():
            (HISTORY_DIR / f"baskio_dashboard_{ts}.html").write_bytes(CURRENT_HTML.read_bytes())
        CURRENT_HTML.write_text(html, encoding="utf-8")
        CURRENT_DATASET.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        write_entry(CHANGELOG_PATH, summary, status="PROMOVIDO")
        log(f"Promoted new dashboard -> {CURRENT_HTML}")
        for line in summary:
            log(f"  · {line}")
        return True

    except Exception as e:
        log(f"BUILD ERROR: {e}")
        log(traceback.format_exc())
        write_entry(CHANGELOG_PATH, [], status="ERROR", issues=[str(e)])
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None, help="Override BASKIO_DSN/SUPABASE_DSN env var")
    ap.add_argument("--dry-run", action="store_true", help="Validate but never promote")
    args = ap.parse_args()

    ok = run_once(dsn=args.dsn, dry_run=args.dry_run)
    sys.exit(0 if ok or args.dry_run else 1)


if __name__ == "__main__":
    main()
